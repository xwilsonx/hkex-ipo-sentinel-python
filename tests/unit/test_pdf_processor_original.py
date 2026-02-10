"""
Unit tests for the original PDFProcessor (pdf_processor.py).
All external dependencies are mocked.
"""
import asyncio
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from pdf_processor.core.pdf_processor import PDFProcessor as OriginalPDFProcessor
from tests.unit.conftest import MockUploadFile, write_section_file, write_toc_file


# ===== Helper to get the *original* class (not the alias) =====
# pdf_processor.py line 15 defines the class directly as PDFProcessor.
# However pdf_processor_final.py re-aliases PDFProcessor = PDFProcessorChunks.
# We import from the original module explicitly to ensure we test the right class.


# ==========================================================================
# Initialization
# ==========================================================================
class TestInit:
    def test_default_data_dir(self, tmp_path):
        data_dir = tmp_path / "data"
        proc = OriginalPDFProcessor(data_dir=str(data_dir))
        assert proc.data_dir == data_dir
        assert data_dir.exists()

    def test_creates_directory_if_missing(self, tmp_path):
        new_dir = tmp_path / "new_data"
        assert not new_dir.exists()
        OriginalPDFProcessor(data_dir=str(new_dir))
        assert new_dir.exists()


# ==========================================================================
# _get_content_from_pages
# ==========================================================================
class TestGetContentFromPages:
    def test_valid_indices(self, tmp_data_dir):
        proc = OriginalPDFProcessor(data_dir=str(tmp_data_dir))
        all_pages = ["Page 0 content", "Page 1 content", "Page 2 content"]

        result = proc._get_content_from_pages(all_pages, [0, 2])
        assert "Page 0 content" in result
        assert "Page 2 content" in result
        assert "Page 1 content" not in result

    def test_out_of_bounds_ignored(self, tmp_data_dir):
        proc = OriginalPDFProcessor(data_dir=str(tmp_data_dir))
        all_pages = ["Page 0"]

        result = proc._get_content_from_pages(all_pages, [0, 5, 10])
        assert "Page 0" in result

    def test_negative_index_ignored(self, tmp_data_dir):
        proc = OriginalPDFProcessor(data_dir=str(tmp_data_dir))
        all_pages = ["Page 0"]

        result = proc._get_content_from_pages(all_pages, [-1, 0])
        assert "Page 0" in result

    def test_empty_content_skipped(self, tmp_data_dir):
        proc = OriginalPDFProcessor(data_dir=str(tmp_data_dir))
        all_pages = ["Content", "   ", "More content"]

        result = proc._get_content_from_pages(all_pages, [0, 1, 2])
        # Whitespace-only page should be stripped to empty and skipped
        assert "Content" in result
        assert "More content" in result

    def test_empty_pages_list(self, tmp_data_dir):
        proc = OriginalPDFProcessor(data_dir=str(tmp_data_dir))
        result = proc._get_content_from_pages(["A", "B"], [])
        assert result == ""


# ==========================================================================
# get_section_content
# ==========================================================================
class TestGetSectionContent:
    def test_retrieves_content(self, tmp_data_dir):
        proc = OriginalPDFProcessor(data_dir=str(tmp_data_dir))
        write_section_file(tmp_data_dir, "doc1", "section_000_intro", "# Hello")

        assert proc.get_section_content("doc1", "section_000_intro") == "# Hello"

    def test_raises_when_missing(self, tmp_data_dir):
        proc = OriginalPDFProcessor(data_dir=str(tmp_data_dir))
        with pytest.raises(FileNotFoundError):
            proc.get_section_content("no_doc", "no_section")


# ==========================================================================
# get_document_toc
# ==========================================================================
class TestGetDocumentToc:
    def test_retrieves_toc(self, tmp_data_dir):
        proc = OriginalPDFProcessor(data_dir=str(tmp_data_dir))
        entries = [{"level": 1, "title": "A", "page": 1, "section_path": "s"}]
        write_toc_file(tmp_data_dir, "doc1", entries=entries)

        result = proc.get_document_toc("doc1")
        assert result["entries"] == entries

    def test_raises_when_missing(self, tmp_data_dir):
        proc = OriginalPDFProcessor(data_dir=str(tmp_data_dir))
        with pytest.raises(FileNotFoundError):
            proc.get_document_toc("nonexistent")


# ==========================================================================
# _extract_all_pages_async
# ==========================================================================
class TestExtractAllPagesAsync:
    @pytest.mark.asyncio
    async def test_successful_extraction(self, tmp_data_dir):
        proc = OriginalPDFProcessor(data_dir=str(tmp_data_dir))

        with patch("pymupdf4llm.to_markdown", return_value="# Page"):
            result = await proc._extract_all_pages_async("fake.pdf", 3)

        assert len(result) == 3
        assert all(r == "# Page" for r in result)

    @pytest.mark.asyncio
    async def test_exception_returns_empty_string(self, tmp_data_dir):
        proc = OriginalPDFProcessor(data_dir=str(tmp_data_dir))

        with patch("pymupdf4llm.to_markdown", side_effect=Exception("fail")):
            result = await proc._extract_all_pages_async("fake.pdf", 2)

        assert len(result) == 2
        assert all(r == "" for r in result)

    @pytest.mark.asyncio
    async def test_none_result_becomes_empty(self, tmp_data_dir):
        proc = OriginalPDFProcessor(data_dir=str(tmp_data_dir))

        with patch("pymupdf4llm.to_markdown", return_value=None):
            result = await proc._extract_all_pages_async("fake.pdf", 1)

        assert result == [""]


# ==========================================================================
# process_pdf (integration-like with mocks)
# ==========================================================================
class TestProcessPdf:
    @pytest.mark.asyncio
    async def test_with_toc(self, tmp_data_dir, mock_fitz_doc, mock_pymupdf4llm):
        toc = [(1, "Section A", 1), (1, "Section B", 3)]
        mock_fitz_doc(toc=toc, page_count=5)
        mock_pymupdf4llm("# Content")

        proc = OriginalPDFProcessor(data_dir=str(tmp_data_dir))
        mock_file = MockUploadFile()

        result = await proc.process_pdf(mock_file, "with_toc")

        assert "toc" in result
        assert len(result["toc"]) == 2
        assert result["toc"][0]["title"] == "Section A"

    @pytest.mark.asyncio
    async def test_without_toc_creates_full_document(self, tmp_data_dir, mock_fitz_doc, mock_pymupdf4llm):
        mock_fitz_doc(toc=[], page_count=3)
        mock_pymupdf4llm("# Content")

        proc = OriginalPDFProcessor(data_dir=str(tmp_data_dir))
        mock_file = MockUploadFile()

        result = await proc.process_pdf(mock_file, "no_toc")

        assert len(result["toc"]) == 1
        assert result["toc"][0]["title"] == "Full Document"
        assert result["toc"][0]["section_path"] == "section_000_full_document"

    @pytest.mark.asyncio
    async def test_temp_file_cleaned_up(self, tmp_data_dir, mock_fitz_doc, mock_pymupdf4llm):
        mock_fitz_doc(toc=[], page_count=1)
        mock_pymupdf4llm("# Content")

        proc = OriginalPDFProcessor(data_dir=str(tmp_data_dir))
        mock_file = MockUploadFile()

        await proc.process_pdf(mock_file, "cleanup")

        temp_file = tmp_data_dir / "cleanup" / "cleanup_temp.pdf"
        assert not temp_file.exists()

    @pytest.mark.asyncio
    async def test_metadata_saved(self, tmp_data_dir, mock_fitz_doc, mock_pymupdf4llm):
        mock_fitz_doc(toc=[], page_count=1)
        mock_pymupdf4llm("# Content")

        proc = OriginalPDFProcessor(data_dir=str(tmp_data_dir))
        mock_file = MockUploadFile(filename="my_report.pdf")

        await proc.process_pdf(mock_file, "meta_test")

        meta_path = tmp_data_dir / "meta_test" / "metadata.json"
        assert meta_path.exists()
        meta = json.loads(meta_path.read_text())
        assert meta["filename"] == "my_report.pdf"


# ==========================================================================
# _extract_toc_and_sections
# ==========================================================================
class TestExtractTocAndSections:
    @pytest.mark.asyncio
    async def test_last_entry_extends_to_page_count(self, tmp_data_dir, mock_fitz_doc, mock_pymupdf4llm):
        toc = [(1, "Only Section", 1)]
        mock_fitz_doc(toc=toc, page_count=10)
        mock_pymupdf4llm("# Content")

        proc = OriginalPDFProcessor(data_dir=str(tmp_data_dir))

        # We need to create a temp file for the method to read
        doc_dir = tmp_data_dir / "last_entry"
        doc_dir.mkdir()
        temp_pdf = doc_dir / "test.pdf"
        temp_pdf.write_bytes(b"fake")

        result = await proc._extract_toc_and_sections(str(temp_pdf), "last_entry")

        assert len(result) == 1
        assert result[0]["title"] == "Only Section"

    @pytest.mark.asyncio
    async def test_saves_toc_json(self, tmp_data_dir, mock_fitz_doc, mock_pymupdf4llm):
        toc = [(1, "A", 1)]
        mock_fitz_doc(toc=toc, page_count=2)
        mock_pymupdf4llm("# Content")

        proc = OriginalPDFProcessor(data_dir=str(tmp_data_dir))
        doc_dir = tmp_data_dir / "toc_save"
        doc_dir.mkdir()
        temp_pdf = doc_dir / "test.pdf"
        temp_pdf.write_bytes(b"fake")

        await proc._extract_toc_and_sections(str(temp_pdf), "toc_save")

        toc_file = tmp_data_dir / "toc_save" / "toc.json"
        assert toc_file.exists()
        data = json.loads(toc_file.read_text())
        assert "entries" in data
        assert "page_count" in data
