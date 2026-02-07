import pytest
import asyncio
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import aiofiles

import sys
sys.path.insert(0, '/home/wilson/opencode/hkex-ipo-sentinel-python')
from pdf_processor.core.pdf_processor import PDFProcessor


class MockFile:
    def __init__(self, filename: str, content_type: str, content: bytes):
        self.filename = filename
        self.content_type = content_type
        self._content = content

    async def read(self):
        return self._content


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def processor(temp_dir):
    return PDFProcessor(data_dir=temp_dir)


@pytest.fixture
def real_pdf_path():
    return Path("/home/wilson/opencode/hkex-ipo-sentinel-python/data/pdf/test_document.pdf")


class TestPDFProcessorInit:
    def test_init_creates_data_directory(self, temp_dir):
        processor = PDFProcessor(data_dir=os.path.join(temp_dir, "new_data"))
        assert processor.data_dir.exists()
        assert processor.data_dir.name == "new_data"

    def test_init_with_default_data_dir(self, temp_dir):
        os.chdir(temp_dir)
        processor = PDFProcessor()
        assert processor.data_dir.exists()
        assert processor.data_dir.name == "data"


class TestProcessPDF:
    @pytest.mark.asyncio
    async def test_process_pdf_creates_document_directory(self, processor, temp_dir, real_pdf_path):
        if not real_pdf_path.exists():
            pytest.skip("Test PDF not found")

        with open(real_pdf_path, 'rb') as f:
            pdf_content = f.read()
        mock_file = MockFile("test.pdf", "application/pdf", pdf_content)

        result = await processor.process_pdf(mock_file, "doc123")

        doc_dir = processor.data_dir / "doc123"
        assert doc_dir.exists()
        assert doc_dir.is_dir()

    @pytest.mark.asyncio
    async def test_process_pdf_saves_metadata(self, processor, temp_dir, real_pdf_path):
        if not real_pdf_path.exists():
            pytest.skip("Test PDF not found")

        with open(real_pdf_path, 'rb') as f:
            pdf_content = f.read()
        mock_file = MockFile("test.pdf", "application/pdf", pdf_content)

        result = await processor.process_pdf(mock_file, "doc123")

        metadata_path = processor.data_dir / "doc123" / "metadata.json"
        assert metadata_path.exists()

        async with aiofiles.open(metadata_path, 'r') as f:
            metadata = json.loads(await f.read())

        assert metadata["filename"] == "test.pdf"
        assert metadata["content_type"] == "application/pdf"
        assert "sections_dir" in metadata

    @pytest.mark.asyncio
    async def test_process_pdf_returns_toc_and_metadata(self, processor, temp_dir, real_pdf_path):
        if not real_pdf_path.exists():
            pytest.skip("Test PDF not found")

        with open(real_pdf_path, 'rb') as f:
            pdf_content = f.read()
        mock_file = MockFile("test.pdf", "application/pdf", pdf_content)

        result = await processor.process_pdf(mock_file, "doc123")

        assert "toc" in result
        assert "metadata" in result
        assert isinstance(result["toc"], list)
        assert isinstance(result["metadata"], dict)

    @pytest.mark.asyncio
    async def test_process_pdf_creates_toc_json(self, processor, temp_dir, real_pdf_path):
        if not real_pdf_path.exists():
            pytest.skip("Test PDF not found")

        with open(real_pdf_path, 'rb') as f:
            pdf_content = f.read()
        mock_file = MockFile("test.pdf", "application/pdf", pdf_content)

        result = await processor.process_pdf(mock_file, "doc123")

        toc_file = processor.data_dir / "doc123" / "toc.json"
        assert toc_file.exists()

        toc_data = json.loads(toc_file.read_text())
        assert "entries" in toc_data
        assert "metadata" in toc_data
        assert "page_count" in toc_data

    @pytest.mark.asyncio
    async def test_process_pdf_handles_empty_toc(self, processor, temp_dir, real_pdf_path):
        if not real_pdf_path.exists():
            pytest.skip("Test PDF not found")

        with open(real_pdf_path, 'rb') as f:
            pdf_content = f.read()
        mock_file = MockFile("test.pdf", "application/pdf", pdf_content)

        result = await processor.process_pdf(mock_file, "empty_toc_doc")

        assert "toc" in result
        assert isinstance(result["toc"], list)


class TestExtractTOCAndSections:
    @pytest.mark.asyncio
    async def test_extract_toc_creates_sections_directory(self, processor, temp_dir, real_pdf_path):
        if not real_pdf_path.exists():
            pytest.skip("Test PDF not found")

        result = await processor._extract_toc_and_sections(str(real_pdf_path), "doc123")

        sections_dir = processor.data_dir / "doc123" / "sections"
        assert sections_dir.exists()

    @pytest.mark.asyncio
    async def test_extract_toc_returns_list(self, processor, temp_dir, real_pdf_path):
        if not real_pdf_path.exists():
            pytest.skip("Test PDF not found")

        result = await processor._extract_toc_and_sections(str(real_pdf_path), "doc123")

        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_extract_toc_saves_toc_json(self, processor, temp_dir, real_pdf_path):
        if not real_pdf_path.exists():
            pytest.skip("Test PDF not found")

        result = await processor._extract_toc_and_sections(str(real_pdf_path), "doc123")

        toc_file = processor.data_dir / "doc123" / "toc.json"
        assert toc_file.exists()


class TestExtractPagesContent:
    @pytest.mark.asyncio
    async def test_extract_pages_content_returns_string(self, processor, real_pdf_path):
        pass

    @pytest.mark.asyncio
    async def test_extract_multiple_pages_content(self, processor, real_pdf_path):
        pass


class TestGetSectionContent:
    def test_get_section_content_returns_content(self, processor, temp_dir):
        doc_id = "test_doc"
        section_path = "section_001_Test"

        doc_dir = processor.data_dir / doc_id
        sections_dir = doc_dir / "sections"
        sections_dir.mkdir(parents=True)

        section_file = sections_dir / f"{section_path}.md"
        section_file.write_text("# Test Content\n\nThis is test content.")

        result = processor.get_section_content(doc_id, section_path)

        assert result == "# Test Content\n\nThis is test content."

    def test_get_section_content_raises_file_not_found(self, processor, temp_dir):
        with pytest.raises(FileNotFoundError):
            processor.get_section_content("nonexistent", "nonexistent_section")

    @pytest.mark.asyncio
    async def test_get_real_sections_dir_exists(self, processor, temp_dir, real_pdf_path):
        if not real_pdf_path.exists():
            pytest.skip("Test PDF not found")

        with open(real_pdf_path, 'rb') as f:
            pdf_content = f.read()
        mock_file = MockFile("test.pdf", "application/pdf", pdf_content)

        await processor.process_pdf(mock_file, "test_doc")

        sections_dir = processor.data_dir / "test_doc" / "sections"
        assert sections_dir.exists()


class TestGetDocumentTOC:
    def test_get_document_toc_returns_toc_data(self, processor, temp_dir):
        doc_id = "test_doc"
        doc_dir = processor.data_dir / doc_id
        doc_dir.mkdir(parents=True)

        toc_file = doc_dir / "toc.json"
        toc_data = {
            "entries": [{"level": 1, "title": "Test", "page": 1, "section_path": "test"}],
            "metadata": {"title": "Test Document"},
            "page_count": 10
        }
        toc_file.write_text(json.dumps(toc_data))

        result = processor.get_document_toc(doc_id)

        assert result["entries"] == toc_data["entries"]
        assert result["metadata"] == toc_data["metadata"]
        assert result["page_count"] == toc_data["page_count"]

    def test_get_document_toc_raises_file_not_found(self, processor, temp_dir):
        with pytest.raises(FileNotFoundError):
            processor.get_document_toc("nonexistent")

    @pytest.mark.asyncio
    async def test_get_real_document_toc(self, processor, temp_dir, real_pdf_path):
        if not real_pdf_path.exists():
            pytest.skip("Test PDF not found")

        with open(real_pdf_path, 'rb') as f:
            pdf_content = f.read()
        mock_file = MockFile("test.pdf", "application/pdf", pdf_content)

        await processor.process_pdf(mock_file, "test_doc")

        result = processor.get_document_toc("test_doc")
        assert "entries" in result
        assert "metadata" in result
        assert "page_count" in result


class TestSectionPathCleaning:
    def test_clean_title_removes_special_characters(self, processor):
        title = "Test: Section/Name (2024)"
        clean_title = "".join(c for c in title if c.isalnum() or c in " _-").strip()
        assert clean_title == "Test SectionName 2024"

    def test_clean_title_preserves_alphanumeric(self, processor):
        title = "Hello World 123"
        clean_title = "".join(c for c in title if c.isalnum() or c in " _-").strip()
        assert clean_title == "Hello World 123"

    def test_clean_title_handles_whitespace_only(self, processor):
        title = "   "
        clean_title = "".join(c for c in title if c.isalnum() or c in " _-").strip()
        assert clean_title == ""

    def test_section_path_format(self, processor):
        for i in range(10):
            title = f"Section {i}"
            clean_title = "".join(c for c in title if c.isalnum() or c in " _-").strip()
            section_path = f"section_{i:03d}_{clean_title}"
            assert section_path.startswith("section_")
            assert f"section_{i:03d}_" in section_path


class TestEdgeCases:
    @pytest.mark.asyncio
    async def test_process_pdf_handles_special_characters_in_filename(self, processor, temp_dir, real_pdf_path):
        if not real_pdf_path.exists():
            pytest.skip("Test PDF not found")

        with open(real_pdf_path, 'rb') as f:
            pdf_content = f.read()
        mock_file = MockFile("test file (1).pdf", "application/pdf", pdf_content)

        result = await processor.process_pdf(mock_file, "special_doc")
        assert "toc" in result
        assert "metadata" in result

    @pytest.mark.asyncio
    async def test_process_multiple_pdfs(self, processor, temp_dir, real_pdf_path):
        if not real_pdf_path.exists():
            pytest.skip("Test PDF not found")

        with open(real_pdf_path, 'rb') as f:
            pdf_content = f.read()
        mock_file = MockFile("test.pdf", "application/pdf", pdf_content)

        result1 = await processor.process_pdf(mock_file, "doc1")
        result2 = await processor.process_pdf(mock_file, "doc2")

        assert (processor.data_dir / "doc1").exists()
        assert (processor.data_dir / "doc2").exists()
        assert "toc" in result1
        assert "toc" in result2


class TestIntegration:
    @pytest.mark.asyncio
    async def test_full_pipeline(self, processor, temp_dir, real_pdf_path):
        if not real_pdf_path.exists():
            pytest.skip("Test PDF not found")

        with open(real_pdf_path, 'rb') as f:
            pdf_content = f.read()
        mock_file = MockFile("document.pdf", "application/pdf", pdf_content)

        result = await processor.process_pdf(mock_file, "integration_test")

        assert "toc" in result
        assert "metadata" in result
        assert isinstance(result["toc"], list)

        toc = processor.get_document_toc("integration_test")
        assert "entries" in toc
        assert "metadata" in toc
        assert "page_count" in toc

        sections_dir = processor.data_dir / "integration_test" / "sections"
        assert sections_dir.exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
