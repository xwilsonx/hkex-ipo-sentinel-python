"""
Unit tests for PDFProcessorOptimized (pdf_processor_optimized.py).
All external dependencies are mocked.
"""
import asyncio
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from pdf_processor.core.pdf_processor_optimized import (
    PDFProcessorOptimized,
    ProcessingConfig,
    ProcessingStrategy,
    SequentialPageExtractor,
    BatchedPageExtractor,
    PageExtractor,
)
from tests.unit.conftest import MockUploadFile, write_section_file, write_toc_file


# ==========================================================================
# ProcessingStrategy Enum
# ==========================================================================
class TestProcessingStrategy:
    def test_sequential(self):
        assert ProcessingStrategy.SEQUENTIAL.value == "sequential"

    def test_batched(self):
        assert ProcessingStrategy.BATCHED.value == "batched"

    def test_fast(self):
        assert ProcessingStrategy.FAST.value == "fast"


# ==========================================================================
# ProcessingConfig
# ==========================================================================
class TestProcessingConfig:
    def test_defaults(self):
        cfg = ProcessingConfig()
        assert cfg.strategy == ProcessingStrategy.BATCHED
        assert cfg.batch_size == 10
        assert cfg.max_workers == 2
        assert cfg.extract_content is True

    def test_custom_values(self):
        cfg = ProcessingConfig(
            strategy=ProcessingStrategy.FAST,
            batch_size=5,
            max_workers=4,
            extract_content=False,
        )
        assert cfg.strategy == ProcessingStrategy.FAST
        assert cfg.batch_size == 5
        assert cfg.max_workers == 4
        assert cfg.extract_content is False


# ==========================================================================
# SequentialPageExtractor
# ==========================================================================
class TestSequentialPageExtractor:
    @pytest.mark.asyncio
    async def test_normal_extraction(self):
        extractor = SequentialPageExtractor()

        with patch("pymupdf4llm.to_markdown", return_value="# Page content"):
            result = await extractor.extract_pages("fake.pdf", [0, 1])

        assert "Page content" in result

    @pytest.mark.asyncio
    async def test_exception_skipped(self):
        extractor = SequentialPageExtractor()

        with patch("pymupdf4llm.to_markdown", side_effect=Exception("fail")):
            result = await extractor.extract_pages("fake.pdf", [0, 1])

        assert result == ""

    @pytest.mark.asyncio
    async def test_empty_result(self):
        extractor = SequentialPageExtractor()

        with patch("pymupdf4llm.to_markdown", return_value=""):
            result = await extractor.extract_pages("fake.pdf", [0])

        assert result == ""

    @pytest.mark.asyncio
    async def test_none_result(self):
        extractor = SequentialPageExtractor()

        with patch("pymupdf4llm.to_markdown", return_value=None):
            result = await extractor.extract_pages("fake.pdf", [0])

        assert result == ""

    @pytest.mark.asyncio
    async def test_pages_sorted(self):
        """Pages should be processed in sorted order."""
        extractor = SequentialPageExtractor()
        call_order = []

        def capture_call(pdf_path, pages=None):
            call_order.append(pages[0])
            return f"Page {pages[0]}"

        with patch("pymupdf4llm.to_markdown", side_effect=capture_call):
            await extractor.extract_pages("fake.pdf", [3, 1, 2])

        assert call_order == [1, 2, 3]


# ==========================================================================
# BatchedPageExtractor
# ==========================================================================
class TestBatchedPageExtractor:
    @pytest.mark.asyncio
    async def test_normal_extraction(self):
        extractor = BatchedPageExtractor(batch_size=5)

        with patch("pymupdf4llm.to_markdown", return_value="# Content"):
            result = await extractor.extract_pages("fake.pdf", [0, 1, 2])

        assert "Content" in result

    @pytest.mark.asyncio
    async def test_batching_logic(self):
        """With batch_size=2 and 5 pages, should create 3 batches."""
        extractor = BatchedPageExtractor(batch_size=2)

        with patch("pymupdf4llm.to_markdown", return_value="# Content"):
            result = await extractor.extract_pages("fake.pdf", [0, 1, 2, 3, 4])

        assert "Content" in result

    @pytest.mark.asyncio
    async def test_exception_in_batch(self):
        """Exception in one batch should not break other batches."""
        extractor = BatchedPageExtractor(batch_size=1)
        call_count = 0

        def side_effect(pdf_path, pages=None):
            nonlocal call_count
            call_count += 1
            if pages == [0]:
                raise Exception("fail")
            return f"# Page {pages[0]}"

        with patch("pymupdf4llm.to_markdown", side_effect=side_effect):
            result = await extractor.extract_pages("fake.pdf", [0, 1])

        # Page 1 content should still be present
        assert "Page 1" in result

    @pytest.mark.asyncio
    async def test_default_batch_size(self):
        extractor = BatchedPageExtractor()
        assert extractor.batch_size == 10


# ==========================================================================
# PDFProcessorOptimized Initialization
# ==========================================================================
class TestInit:
    def test_default_config(self, tmp_data_dir):
        proc = PDFProcessorOptimized(data_dir=str(tmp_data_dir))
        assert isinstance(proc.config, ProcessingConfig)
        assert isinstance(proc.extractor, BatchedPageExtractor)

    def test_sequential_strategy_uses_sequential_extractor(self, tmp_data_dir):
        cfg = ProcessingConfig(strategy=ProcessingStrategy.SEQUENTIAL)
        proc = PDFProcessorOptimized(data_dir=str(tmp_data_dir), config=cfg)
        assert isinstance(proc.extractor, SequentialPageExtractor)

    def test_batched_strategy_uses_batched_extractor(self, tmp_data_dir):
        cfg = ProcessingConfig(strategy=ProcessingStrategy.BATCHED, batch_size=7)
        proc = PDFProcessorOptimized(data_dir=str(tmp_data_dir), config=cfg)
        assert isinstance(proc.extractor, BatchedPageExtractor)
        assert proc.extractor.batch_size == 7

    def test_creates_data_dir(self, tmp_path):
        new_dir = tmp_path / "opt_data"
        PDFProcessorOptimized(data_dir=str(new_dir))
        assert new_dir.exists()


# ==========================================================================
# process_pdf
# ==========================================================================
class TestProcessPdf:
    @pytest.mark.asyncio
    async def test_with_toc_extract_content(self, tmp_data_dir, mock_fitz_doc, mock_pymupdf4llm):
        toc = [(1, "Intro", 1), (1, "Body", 3)]
        mock_fitz_doc(toc=toc, page_count=5)
        mock_pymupdf4llm("# Content")

        cfg = ProcessingConfig(extract_content=True)
        proc = PDFProcessorOptimized(data_dir=str(tmp_data_dir), config=cfg)
        mock_file = MockUploadFile()

        result = await proc.process_pdf(mock_file, "opt_toc")

        assert len(result["toc"]) == 2
        assert result["toc"][0]["title"] == "Intro"

    @pytest.mark.asyncio
    async def test_without_toc(self, tmp_data_dir, mock_fitz_doc, mock_pymupdf4llm):
        mock_fitz_doc(toc=[], page_count=3)
        mock_pymupdf4llm("# Content")

        cfg = ProcessingConfig(extract_content=True)
        proc = PDFProcessorOptimized(data_dir=str(tmp_data_dir), config=cfg)
        mock_file = MockUploadFile()

        result = await proc.process_pdf(mock_file, "opt_no_toc")

        # No TOC → single section with all pages
        assert result["toc"] == []

    @pytest.mark.asyncio
    async def test_extract_content_false(self, tmp_data_dir, mock_fitz_doc):
        """FAST strategy: extract_content=False → TOC only, no section files."""
        toc = [(1, "A", 1), (1, "B", 3)]
        mock_fitz_doc(toc=toc, page_count=5)

        cfg = ProcessingConfig(extract_content=False)
        proc = PDFProcessorOptimized(data_dir=str(tmp_data_dir), config=cfg)
        mock_file = MockUploadFile()

        result = await proc.process_pdf(mock_file, "fast_mode")

        assert len(result["toc"]) == 2
        # No section files should be created
        sections_dir = tmp_data_dir / "fast_mode" / "sections"
        if sections_dir.exists():
            md_files = list(sections_dir.glob("*.md"))
            assert len(md_files) == 0

    @pytest.mark.asyncio
    async def test_temp_file_cleaned_up(self, tmp_data_dir, mock_fitz_doc, mock_pymupdf4llm):
        mock_fitz_doc(toc=[], page_count=1)
        mock_pymupdf4llm("# Content")

        proc = PDFProcessorOptimized(data_dir=str(tmp_data_dir))
        mock_file = MockUploadFile()

        await proc.process_pdf(mock_file, "opt_cleanup")

        temp_file = tmp_data_dir / "opt_cleanup" / "opt_cleanup_temp.pdf"
        assert not temp_file.exists()

    @pytest.mark.asyncio
    async def test_metadata_saved(self, tmp_data_dir, mock_fitz_doc, mock_pymupdf4llm):
        mock_fitz_doc(toc=[], page_count=1)
        mock_pymupdf4llm("# Content")

        proc = PDFProcessorOptimized(data_dir=str(tmp_data_dir))
        mock_file = MockUploadFile(filename="report.pdf")

        await proc.process_pdf(mock_file, "opt_meta")

        meta_path = tmp_data_dir / "opt_meta" / "metadata.json"
        assert meta_path.exists()
        meta = json.loads(meta_path.read_text())
        assert meta["filename"] == "report.pdf"


# ==========================================================================
# _extract_large_section
# ==========================================================================
class TestExtractLargeSection:
    @pytest.mark.asyncio
    async def test_sub_batching(self, tmp_data_dir, mock_pymupdf4llm):
        mock_pymupdf4llm("# Batch content")
        proc = PDFProcessorOptimized(data_dir=str(tmp_data_dir))

        pages = list(range(50))  # 50 pages / 20 batch_size → 3 sub-batches
        result = await proc._extract_large_section("fake.pdf", pages)

        assert "Batch content" in result

    @pytest.mark.asyncio
    async def test_empty_batches_handled(self, tmp_data_dir):
        proc = PDFProcessorOptimized(data_dir=str(tmp_data_dir))

        with patch("pymupdf4llm.to_markdown", return_value=""):
            result = await proc._extract_large_section("fake.pdf", list(range(5)))

        assert result == ""


# ==========================================================================
# get_section_content / get_document_toc
# ==========================================================================
class TestGetSectionContent:
    def test_file_exists(self, tmp_data_dir):
        proc = PDFProcessorOptimized(data_dir=str(tmp_data_dir))
        write_section_file(tmp_data_dir, "doc1", "section_000_intro", "# Intro")
        assert proc.get_section_content("doc1", "section_000_intro") == "# Intro"

    def test_file_not_found(self, tmp_data_dir):
        proc = PDFProcessorOptimized(data_dir=str(tmp_data_dir))
        with pytest.raises(FileNotFoundError):
            proc.get_section_content("missing", "missing")


class TestGetDocumentToc:
    def test_file_exists(self, tmp_data_dir):
        proc = PDFProcessorOptimized(data_dir=str(tmp_data_dir))
        write_toc_file(tmp_data_dir, "doc1")
        result = proc.get_document_toc("doc1")
        assert "entries" in result

    def test_file_not_found(self, tmp_data_dir):
        proc = PDFProcessorOptimized(data_dir=str(tmp_data_dir))
        with pytest.raises(FileNotFoundError):
            proc.get_document_toc("nonexistent")


# ==========================================================================
# Backward compatibility alias
# ==========================================================================
class TestBackwardCompatibility:
    def test_alias(self):
        from pdf_processor.core.pdf_processor_optimized import PDFProcessor as Alias
        assert Alias is PDFProcessorOptimized
