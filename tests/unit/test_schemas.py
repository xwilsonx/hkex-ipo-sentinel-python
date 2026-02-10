"""
Unit tests for Pydantic schemas (pdf_processor/models/schemas.py).
"""
import pytest
from pydantic import ValidationError

from pdf_processor.models.schemas import (
    TOCEntry,
    FileEntry,
    TOCResponse,
    SectionContent,
)


# ==========================================================================
# TOCEntry
# ==========================================================================
class TestTOCEntry:
    def test_valid_construction(self):
        entry = TOCEntry(level=1, title="Introduction", page=1, section_path="section_000_intro")
        assert entry.level == 1
        assert entry.title == "Introduction"
        assert entry.page == 1
        assert entry.section_path == "section_000_intro"

    def test_missing_required_field(self):
        with pytest.raises(ValidationError):
            TOCEntry(level=1, title="A", page=1)  # missing section_path

    def test_type_coercion(self):
        """Pydantic should coerce string numbers to int."""
        entry = TOCEntry(level="2", title="Ch", page="5", section_path="s")
        assert entry.level == 2
        assert entry.page == 5

    def test_all_fields_required(self):
        with pytest.raises(ValidationError):
            TOCEntry()


# ==========================================================================
# FileEntry
# ==========================================================================
class TestFileEntry:
    def test_valid_construction(self):
        entry = FileEntry(name="intro.json", url="/api/v1/document/d/section/s")
        assert entry.name == "intro.json"
        assert entry.url == "/api/v1/document/d/section/s"

    def test_missing_name(self):
        with pytest.raises(ValidationError):
            FileEntry(url="/api/v1/document/d/section/s")

    def test_missing_url(self):
        with pytest.raises(ValidationError):
            FileEntry(name="file.json")


# ==========================================================================
# TOCResponse
# ==========================================================================
class TestTOCResponse:
    def test_full_valid_payload(self):
        resp = TOCResponse(
            document_id="doc1",
            toc=[
                TOCEntry(level=1, title="A", page=1, section_path="s1"),
                TOCEntry(level=2, title="B", page=3, section_path="s2"),
            ],
            files=[
                FileEntry(name="A.json", url="/api/v1/document/doc1/section/s1"),
            ],
            metadata={"filename": "test.pdf", "pages": 10},
        )
        assert resp.document_id == "doc1"
        assert len(resp.toc) == 2
        assert len(resp.files) == 1
        assert resp.metadata["pages"] == 10

    def test_empty_toc_and_files(self):
        resp = TOCResponse(
            document_id="doc2",
            toc=[],
            files=[],
            metadata={},
        )
        assert resp.toc == []
        assert resp.files == []

    def test_missing_document_id(self):
        with pytest.raises(ValidationError):
            TOCResponse(toc=[], files=[], metadata={})

    def test_missing_metadata(self):
        with pytest.raises(ValidationError):
            TOCResponse(document_id="d", toc=[], files=[])

    def test_serialization(self):
        resp = TOCResponse(
            document_id="d",
            toc=[TOCEntry(level=1, title="T", page=1, section_path="s")],
            files=[FileEntry(name="T.json", url="/u")],
            metadata={"key": "value"},
        )
        data = resp.model_dump()
        assert isinstance(data, dict)
        assert data["document_id"] == "d"
        assert len(data["toc"]) == 1


# ==========================================================================
# SectionContent
# ==========================================================================
class TestSectionContent:
    def test_valid_construction(self):
        sc = SectionContent(content="# Hello", section_path="section_000_hello")
        assert sc.content == "# Hello"
        assert sc.section_path == "section_000_hello"

    def test_empty_content(self):
        sc = SectionContent(content="", section_path="s")
        assert sc.content == ""

    def test_missing_content(self):
        with pytest.raises(ValidationError):
            SectionContent(section_path="s")

    def test_missing_section_path(self):
        with pytest.raises(ValidationError):
            SectionContent(content="hello")
