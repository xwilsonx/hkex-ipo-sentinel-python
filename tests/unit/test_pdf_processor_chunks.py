"""
Comprehensive unit tests for PDFProcessorChunks (pdf_processor_final.py).
All external dependencies (fitz, pymupdf4llm, aiofiles) are mocked.
"""
import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, mock_open

import pytest

from pdf_processor.core.pdf_processor_final import (
    PDFProcessorChunks,
    SectionChunkStrategy,
)
from tests.unit.conftest import MockUploadFile, write_section_file, write_toc_file


# ==========================================================================
# SectionChunkStrategy
# ==========================================================================
class TestSectionChunkStrategy:
    """Verify strategy constants."""

    def test_by_toc(self):
        assert SectionChunkStrategy.BY_TOC == "by_toc"

    def test_by_pages(self):
        assert SectionChunkStrategy.BY_PAGES == "by_pages"

    def test_by_toc_chunked(self):
        assert SectionChunkStrategy.BY_TOC_CHUNKED == "by_toc_chunked"


# ==========================================================================
# Initialization
# ==========================================================================
class TestInit:
    """Test PDFProcessorChunks.__init__."""

    def test_default_params(self, tmp_data_dir):
        proc = PDFProcessorChunks(data_dir=str(tmp_data_dir))
        assert proc.data_dir == tmp_data_dir
        assert proc.strategy == SectionChunkStrategy.BY_PAGES
        assert proc.pages_per_chunk == 15
        assert proc.max_section_size == 50

    def test_custom_params(self, tmp_data_dir):
        proc = PDFProcessorChunks(
            data_dir=str(tmp_data_dir),
            strategy=SectionChunkStrategy.BY_TOC,
            pages_per_chunk=5,
            max_section_size=20,
        )
        assert proc.strategy == SectionChunkStrategy.BY_TOC
        assert proc.pages_per_chunk == 5
        assert proc.max_section_size == 20

    def test_creates_data_directory(self, tmp_path):
        new_dir = tmp_path / "new_data"
        assert not new_dir.exists()
        PDFProcessorChunks(data_dir=str(new_dir))
        assert new_dir.exists()


# ==========================================================================
# process_pdf
# ==========================================================================
class TestProcessPdf:
    """Test the main process_pdf entry point."""

    @pytest.mark.asyncio
    async def test_creates_document_directory(self, tmp_data_dir, mock_fitz_doc, mock_pymupdf4llm):
        mock_fitz_doc(toc=[], page_count=1)
        mock_pymupdf4llm("# Content")
        proc = PDFProcessorChunks(data_dir=str(tmp_data_dir))
        mock_file = MockUploadFile(content=b"fake-pdf")

        result = await proc.process_pdf(mock_file, "doc1")

        doc_dir = tmp_data_dir / "doc1"
        assert doc_dir.exists()
        assert "toc" in result
        assert "metadata" in result

    @pytest.mark.asyncio
    async def test_saves_metadata_json(self, tmp_data_dir, mock_fitz_doc, mock_pymupdf4llm):
        mock_fitz_doc(toc=[], page_count=1)
        mock_pymupdf4llm("# Content")
        proc = PDFProcessorChunks(data_dir=str(tmp_data_dir))
        mock_file = MockUploadFile(filename="report.pdf", content_type="application/pdf")

        await proc.process_pdf(mock_file, "doc_meta")

        meta_path = tmp_data_dir / "doc_meta" / "metadata.json"
        assert meta_path.exists()
        meta = json.loads(meta_path.read_text())
        assert meta["filename"] == "report.pdf"
        assert meta["content_type"] == "application/pdf"
        assert "strategy" in meta
        assert "total_pages" in meta

    @pytest.mark.asyncio
    async def test_cleans_up_temp_file(self, tmp_data_dir, mock_fitz_doc, mock_pymupdf4llm):
        mock_fitz_doc(toc=[], page_count=1)
        mock_pymupdf4llm("# Content")
        proc = PDFProcessorChunks(data_dir=str(tmp_data_dir))
        mock_file = MockUploadFile()

        await proc.process_pdf(mock_file, "cleanup_test")

        temp_pdf = tmp_data_dir / "cleanup_test" / "cleanup_test_temp.pdf"
        assert not temp_pdf.exists()

    @pytest.mark.asyncio
    async def test_returns_toc_and_metadata(self, tmp_data_dir, mock_fitz_doc, mock_pymupdf4llm):
        toc = [(1, "Introduction", 1), (1, "Chapter 1", 3)]
        mock_fitz_doc(toc=toc, page_count=5)
        mock_pymupdf4llm("# Page content")
        proc = PDFProcessorChunks(
            data_dir=str(tmp_data_dir),
            strategy=SectionChunkStrategy.BY_PAGES,
            pages_per_chunk=10,
        )
        mock_file = MockUploadFile()

        result = await proc.process_pdf(mock_file, "result_test")

        assert isinstance(result["toc"], list)
        assert len(result["toc"]) > 0
        assert isinstance(result["metadata"], dict)


# ==========================================================================
# BY_PAGES Strategy (_create_page_chunks)
# ==========================================================================
class TestByPagesStrategy:
    """Test the BY_PAGES chunking strategy."""

    @pytest.mark.asyncio
    async def test_single_chunk_small_doc(self, tmp_data_dir, mock_fitz_doc, mock_pymupdf4llm):
        mock_fitz_doc(toc=[], page_count=3)
        mock_pymupdf4llm("# Content")
        proc = PDFProcessorChunks(
            data_dir=str(tmp_data_dir),
            strategy=SectionChunkStrategy.BY_PAGES,
            pages_per_chunk=10,
        )
        mock_file = MockUploadFile()

        result = await proc.process_pdf(mock_file, "single_chunk")
        toc = result["toc"]
        # 3 pages with chunk size 10 → 1 chunk
        assert len(toc) == 1
        assert toc[0]["page_range"] == [1, 3]

    @pytest.mark.asyncio
    async def test_multiple_chunks(self, tmp_data_dir, mock_fitz_doc, mock_pymupdf4llm):
        mock_fitz_doc(toc=[], page_count=25)
        mock_pymupdf4llm("# Content")
        proc = PDFProcessorChunks(
            data_dir=str(tmp_data_dir),
            strategy=SectionChunkStrategy.BY_PAGES,
            pages_per_chunk=10,
        )
        mock_file = MockUploadFile()

        result = await proc.process_pdf(mock_file, "multi_chunk")
        toc = result["toc"]
        # 25 pages / 10 per chunk → 3 chunks
        assert len(toc) == 3
        assert toc[0]["page_range"] == [1, 10]
        assert toc[1]["page_range"] == [11, 20]
        assert toc[2]["page_range"] == [21, 25]

    @pytest.mark.asyncio
    async def test_related_toc_entries(self, tmp_data_dir, mock_fitz_doc, mock_pymupdf4llm):
        toc = [(1, "Intro", 1), (1, "Chapter 1", 5)]
        mock_fitz_doc(toc=toc, page_count=10)
        mock_pymupdf4llm("# Content")
        proc = PDFProcessorChunks(
            data_dir=str(tmp_data_dir),
            strategy=SectionChunkStrategy.BY_PAGES,
            pages_per_chunk=10,
        )
        mock_file = MockUploadFile()

        result = await proc.process_pdf(mock_file, "related_toc")
        entry = result["toc"][0]
        assert "related_toc" in entry
        assert isinstance(entry["related_toc"], list)

    @pytest.mark.asyncio
    async def test_section_files_written_to_disk(self, tmp_data_dir, mock_fitz_doc, mock_pymupdf4llm):
        mock_fitz_doc(toc=[], page_count=5)
        mock_pymupdf4llm("# Content")
        proc = PDFProcessorChunks(
            data_dir=str(tmp_data_dir),
            strategy=SectionChunkStrategy.BY_PAGES,
            pages_per_chunk=5,
        )
        mock_file = MockUploadFile()

        result = await proc.process_pdf(mock_file, "disk_test")
        sections_dir = tmp_data_dir / "disk_test" / "sections"
        assert sections_dir.exists()
        md_files = list(sections_dir.glob("*.md"))
        assert len(md_files) == 1


# ==========================================================================
# BY_TOC_CHUNKED Strategy (_create_toc_chunked)
# ==========================================================================
class TestByTocChunkedStrategy:
    """Test the BY_TOC_CHUNKED chunking strategy."""

    @pytest.mark.asyncio
    async def test_normal_sections(self, tmp_data_dir, mock_fitz_doc, mock_pymupdf4llm):
        toc = [(1, "Section A", 1), (1, "Section B", 3)]
        mock_fitz_doc(toc=toc, page_count=5)
        mock_pymupdf4llm("# Content")
        proc = PDFProcessorChunks(
            data_dir=str(tmp_data_dir),
            strategy=SectionChunkStrategy.BY_TOC_CHUNKED,
            max_section_size=50,
            pages_per_chunk=15,
        )
        mock_file = MockUploadFile()

        result = await proc.process_pdf(mock_file, "toc_chunked_normal")
        toc_entries = result["toc"]
        assert len(toc_entries) == 2
        assert toc_entries[0]["title"] == "Section A"
        assert toc_entries[1]["title"] == "Section B"

    @pytest.mark.asyncio
    async def test_large_section_split(self, tmp_data_dir, mock_fitz_doc, mock_pymupdf4llm):
        """A section spanning > max_section_size pages should be split."""
        toc = [(1, "Huge Section", 1)]
        mock_fitz_doc(toc=toc, page_count=100)
        mock_pymupdf4llm("# Content")
        proc = PDFProcessorChunks(
            data_dir=str(tmp_data_dir),
            strategy=SectionChunkStrategy.BY_TOC_CHUNKED,
            max_section_size=10,
            pages_per_chunk=5,
        )
        mock_file = MockUploadFile()

        result = await proc.process_pdf(mock_file, "toc_chunked_large")
        toc_entries = result["toc"]
        # 100 pages / 5 per chunk → 20 parts
        assert len(toc_entries) == 20
        assert "Part 1/" in toc_entries[0]["title"]
        assert toc_entries[0].get("parent_title") == "Huge Section"


# ==========================================================================
# BY_TOC Strategy (_create_toc_based)
# ==========================================================================
class TestByTocStrategy:
    """Test the original TOC-based strategy."""

    @pytest.mark.asyncio
    async def test_standard_toc(self, tmp_data_dir, mock_fitz_doc, mock_pymupdf4llm):
        toc = [(1, "Intro", 1), (1, "Body", 3), (1, "End", 5)]
        mock_fitz_doc(toc=toc, page_count=6)
        mock_pymupdf4llm("# Content")
        proc = PDFProcessorChunks(
            data_dir=str(tmp_data_dir),
            strategy=SectionChunkStrategy.BY_TOC,
        )
        mock_file = MockUploadFile()

        result = await proc.process_pdf(mock_file, "toc_based")
        toc_entries = result["toc"]
        assert len(toc_entries) == 3
        assert toc_entries[0]["title"] == "Intro"
        assert toc_entries[2]["title"] == "End"

    @pytest.mark.asyncio
    async def test_empty_pages_skipped(self, tmp_data_dir, mock_fitz_doc, mock_pymupdf4llm):
        """When two TOC entries point to the same page, the first has no pages."""
        toc = [(1, "A", 3), (1, "B", 3)]
        mock_fitz_doc(toc=toc, page_count=5)
        mock_pymupdf4llm("# Content")
        proc = PDFProcessorChunks(
            data_dir=str(tmp_data_dir),
            strategy=SectionChunkStrategy.BY_TOC,
        )
        mock_file = MockUploadFile()

        result = await proc.process_pdf(mock_file, "empty_pages")
        # First entry "A" has page range(2,2)=[] which is empty → skipped
        # Only "B" has pages → 1 entry
        assert len(result["toc"]) == 1
        assert result["toc"][0]["title"] == "B"


# ==========================================================================
# _chunk_large_section
# ==========================================================================
class TestChunkLargeSection:
    """Test _chunk_large_section directly."""

    @pytest.mark.asyncio
    async def test_correct_chunk_count(self, tmp_data_dir, mock_pymupdf4llm):
        mock_pymupdf4llm("# Content")
        proc = PDFProcessorChunks(
            data_dir=str(tmp_data_dir),
            pages_per_chunk=5,
        )
        sections_dir = tmp_data_dir / "chunk_test" / "sections"
        sections_dir.mkdir(parents=True)

        pages = list(range(23))  # 23 pages → 5 chunks
        entries, counter = await proc._chunk_large_section(
            "fake.pdf", sections_dir, pages, level=1, title="Big", section_counter=0
        )

        assert len(entries) == 5
        assert counter == 5

    @pytest.mark.asyncio
    async def test_part_numbering(self, tmp_data_dir, mock_pymupdf4llm):
        mock_pymupdf4llm("# Content")
        proc = PDFProcessorChunks(
            data_dir=str(tmp_data_dir),
            pages_per_chunk=10,
        )
        sections_dir = tmp_data_dir / "part_num" / "sections"
        sections_dir.mkdir(parents=True)

        pages = list(range(25))  # 3 parts
        entries, _ = await proc._chunk_large_section(
            "fake.pdf", sections_dir, pages, level=2, title="Title", section_counter=0
        )

        assert entries[0]["title"] == "Title (Part 1/3)"
        assert entries[1]["title"] == "Title (Part 2/3)"
        assert entries[2]["title"] == "Title (Part 3/3)"
        assert all(e.get("parent_title") == "Title" for e in entries)


# ==========================================================================
# _extract_chunk_content
# ==========================================================================
class TestExtractChunkContent:
    """Test page content extraction."""

    @pytest.mark.asyncio
    async def test_successful_extraction(self, tmp_data_dir, mock_pymupdf4llm):
        mock_to_md = mock_pymupdf4llm("# Page content")
        proc = PDFProcessorChunks(data_dir=str(tmp_data_dir))

        content = await proc._extract_chunk_content("fake.pdf", [0, 1, 2])

        assert "Page content" in content
        assert mock_to_md.call_count == 3

    @pytest.mark.asyncio
    async def test_exception_skipped(self, tmp_data_dir):
        """Extraction errors on individual pages should be logged and skipped."""
        proc = PDFProcessorChunks(data_dir=str(tmp_data_dir))

        with patch("pymupdf4llm.to_markdown", side_effect=Exception("timeout")):
            content = await proc._extract_chunk_content("fake.pdf", [0, 1])

        assert content == ""

    @pytest.mark.asyncio
    async def test_empty_result(self, tmp_data_dir):
        proc = PDFProcessorChunks(data_dir=str(tmp_data_dir))

        with patch("pymupdf4llm.to_markdown", return_value=""):
            content = await proc._extract_chunk_content("fake.pdf", [0])

        assert content == ""

    @pytest.mark.asyncio
    async def test_none_result(self, tmp_data_dir):
        proc = PDFProcessorChunks(data_dir=str(tmp_data_dir))

        with patch("pymupdf4llm.to_markdown", return_value=None):
            content = await proc._extract_chunk_content("fake.pdf", [0])

        assert content == ""


# ==========================================================================
# _find_toc_entries_for_pages
# ==========================================================================
class TestFindTocEntriesForPages:
    """Test TOC-to-page mapping."""

    def test_match_on_page_index(self, tmp_data_dir):
        proc = PDFProcessorChunks(data_dir=str(tmp_data_dir))
        toc = [(1, "A", 1), (1, "B", 5), (2, "C", 10)]
        pages = [0, 1, 2, 3]  # pages 0-3 (page_idx)

        result = proc._find_toc_entries_for_pages(toc, pages)
        # A is at page 1 → idx 0, which is in pages
        assert len(result) >= 1
        assert result[0][1] == "A"

    def test_no_matches(self, tmp_data_dir):
        proc = PDFProcessorChunks(data_dir=str(tmp_data_dir))
        toc = [(1, "A", 50)]
        pages = [0, 1, 2]

        result = proc._find_toc_entries_for_pages(toc, pages)
        assert result == []

    def test_empty_toc(self, tmp_data_dir):
        proc = PDFProcessorChunks(data_dir=str(tmp_data_dir))
        result = proc._find_toc_entries_for_pages([], [0, 1])
        assert result == []

    def test_empty_pages(self, tmp_data_dir):
        proc = PDFProcessorChunks(data_dir=str(tmp_data_dir))
        toc = [(1, "A", 1)]
        result = proc._find_toc_entries_for_pages(toc, [])
        assert result == []


# ==========================================================================
# _clean_title
# ==========================================================================
class TestCleanTitle:
    """Test filename-safe title cleaning."""

    def test_alphanumeric_passthrough(self, tmp_data_dir):
        proc = PDFProcessorChunks(data_dir=str(tmp_data_dir))
        assert proc._clean_title("HelloWorld") == "HelloWorld"

    def test_special_chars_stripped(self, tmp_data_dir):
        proc = PDFProcessorChunks(data_dir=str(tmp_data_dir))
        assert proc._clean_title("Hello@#$World!") == "HelloWorld"

    def test_allowed_chars_preserved(self, tmp_data_dir):
        proc = PDFProcessorChunks(data_dir=str(tmp_data_dir))
        result = proc._clean_title("Hello World_test-case")
        assert result == "Hello World_test-case"

    def test_long_title_truncated(self, tmp_data_dir):
        proc = PDFProcessorChunks(data_dir=str(tmp_data_dir))
        long_title = "A" * 100
        result = proc._clean_title(long_title)
        assert len(result) <= 50

    def test_whitespace_trimmed(self, tmp_data_dir):
        proc = PDFProcessorChunks(data_dir=str(tmp_data_dir))
        result = proc._clean_title("  spaces  ")
        assert result == "spaces"

    def test_empty_string(self, tmp_data_dir):
        proc = PDFProcessorChunks(data_dir=str(tmp_data_dir))
        result = proc._clean_title("")
        assert result == ""


# ==========================================================================
# get_section_content
# ==========================================================================
class TestGetSectionContent:
    """Test section content retrieval from disk."""

    def test_file_exists(self, tmp_data_dir):
        proc = PDFProcessorChunks(data_dir=str(tmp_data_dir))
        write_section_file(tmp_data_dir, "doc1", "section_000_intro", "# Introduction")

        content = proc.get_section_content("doc1", "section_000_intro")
        assert content == "# Introduction"

    def test_file_not_found(self, tmp_data_dir):
        proc = PDFProcessorChunks(data_dir=str(tmp_data_dir))
        with pytest.raises(FileNotFoundError, match="Section content not found"):
            proc.get_section_content("missing_doc", "section_000_intro")


# ==========================================================================
# get_document_toc
# ==========================================================================
class TestGetDocumentToc:
    """Test TOC retrieval from disk."""

    def test_file_exists(self, tmp_data_dir):
        proc = PDFProcessorChunks(data_dir=str(tmp_data_dir))
        entries = [{"level": 1, "title": "Test", "page": 1, "section_path": "s"}]
        write_toc_file(tmp_data_dir, "doc1", entries=entries, page_count=10)

        result = proc.get_document_toc("doc1")
        assert result["entries"] == entries
        assert result["page_count"] == 10

    def test_file_not_found(self, tmp_data_dir):
        proc = PDFProcessorChunks(data_dir=str(tmp_data_dir))
        with pytest.raises(FileNotFoundError, match="Document TOC not found"):
            proc.get_document_toc("nonexistent")


# ==========================================================================
# Backward compatibility alias
# ==========================================================================
class TestBackwardCompatibility:
    """The module aliases PDFProcessor = PDFProcessorChunks."""

    def test_alias_exists(self):
        from pdf_processor.core.pdf_processor_final import PDFProcessor
        assert PDFProcessor is PDFProcessorChunks
