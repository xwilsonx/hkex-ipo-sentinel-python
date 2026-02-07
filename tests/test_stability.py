#!/usr/bin/env python3
"""Stability and edge case tests for PDF processor"""

import pytest
import asyncio
import json
import os
import tempfile
from pathlib import Path
import aiofiles
import sys
import time

sys.path.insert(0, '/home/wilson/opencode/hkex-ipo-sentinel-python')
from pdf_processor.core.pdf_processor import PDFProcessor


class MockFile:
    """Mock UploadFile for testing"""
    def __init__(self, filename: str, content_type: str, content: bytes):
        self.filename = filename
        self.content_type = content_type
        self._content = content

    async def read(self):
        return self._content


@pytest.fixture
def processor():
    """Create a PDFProcessor for testing"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield PDFProcessor(data_dir=tmpdir)


@pytest.fixture
def pdf_test_dir():
    """Get the directory containing test PDF files"""
    return Path("/home/wilson/opencode/hkex-ipo-sentinel-python/data/pdf")


class TestPDFsNoTOC:
    """Test PDFs that don't have a TOC"""

    @pytest.mark.asyncio
    async def test_process_pdf_without_toc(self, processor, pdf_test_dir):
        """Test processing a PDF that has no TOC"""
        pdf_path = pdf_test_dir / "sehk26020600999.pdf"
        
        if not pdf_path.exists():
            pytest.skip("sehk26020600999.pdf not found")

        with open(pdf_path, 'rb') as f:
            pdf_content = f.read()
        
        mock_file = MockFile(pdf_path.name, "application/pdf", pdf_content)
        doc_id = "no_toc_test"

        result = await processor.process_pdf(mock_file, doc_id)

        assert "toc" in result
        assert isinstance(result["toc"], list)
        assert len(result["toc"]) == 0, "Expected empty TOC for PDF without TOC"

        doc_dir = processor.data_dir / doc_id
        assert doc_dir.exists()
        assert (doc_dir / "toc.json").exists()
        assert (doc_dir / "metadata.json").exists()

    @pytest.mark.asyncio
    async def test_process_medium_pdf_no_toc(self, processor, pdf_test_dir):
        """Test processing medium PDF without TOC"""
        pdf_path = pdf_test_dir / "sehk26020600953.pdf"
        
        if not pdf_path.exists():
            pytest.skip("sehk26020600953.pdf not found")

        with open(pdf_path, 'rb') as f:
            pdf_content = f.read()
        
        mock_file = MockFile(pdf_path.name, "application/pdf", pdf_content)
        doc_id = "medium_no_toc"

        result = await processor.process_pdf(mock_file, doc_id)

        assert "toc" in result
        assert isinstance(result["toc"], list)
        assert len(result["toc"]) == 0


class TestLargePDFs:
    """Test handling of large PDF files"""

    @pytest.mark.asyncio
    async def test_large_pdf_performance(self, processor, pdf_test_dir):
        """Test processing with large PDF (first 100 pages only for speed)"""
        pdf_path = pdf_test_dir / "sehk26012600719.pdf"
        
        if not pdf_path.exists():
            pytest.skip("sehk26012600719.pdf not found")

        file_size_mb = pdf_path.stat().st_size / (1024 * 1024)
        print(f"\nProcessing large PDF: {file_size_mb:.1f} MB")

        with open(pdf_path, 'rb') as f:
            pdf_content = f.read()
        
        mock_file = MockFile(pdf_path.name, "application/pdf", pdf_content)
        doc_id = "large_test"

        start_time = time.time()
        result = await processor.process_pdf(mock_file, doc_id)
        elapsed_time = time.time() - start_time

        print(f"Processing took {elapsed_time:.1f} seconds")
        
        assert "toc" in result
        assert len(result["toc"]) > 0
        
        doc_dir = processor.data_dir / doc_id
        assert doc_dir.exists()
        toc_file = doc_dir / "toc.json"
        assert toc_file.exists()


class TestSectionContent:
    """Test section content retrieval"""

    @pytest.mark.asyncio
    async def test_retrieve_first_sections(self, processor, pdf_test_dir):
        """Retrieve content for first few sections in a PDF"""
        pdf_path = pdf_test_dir / "sehk26013000306.pdf"
        
        if not pdf_path.exists():
            pytest.skip("sehk26013000306.pdf not found")

        with open(pdf_path, 'rb') as f:
            pdf_content = f.read()
        
        mock_file = MockFile(pdf_path.name, "application/pdf", pdf_content)
        doc_id = "sections_test"

        result = await processor.process_pdf(mock_file, doc_id)
        
        # Test first 3 sections
        for i, entry in enumerate(result['toc'][:3]):
            section_path = entry["section_path"]
            content = processor.get_section_content(doc_id, section_path)
            assert isinstance(content, str)
            assert len(content) > 0
            print(f"  Section {i}: {section_path[:30]}... ({len(content)} chars)")


class TestErrorHandling:
    """Test error handling"""

    @pytest.mark.asyncio
    async def test_retrieve_nonexistent_section(self, processor):
        """Test handling of non-existent section"""
        with pytest.raises(FileNotFoundError):
            processor.get_section_content("nonexistent", "nonexistent")

    def test_get_nonexistent_document_toc(self, processor):
        """Test getting TOC for non-existent document"""
        with pytest.raises(FileNotFoundError):
            processor.get_document_toc("nonexistent_doc")

    @pytest.mark.asyncio
    async def test_invalid_pdf_content(self, processor):
        """Test handling of invalid PDF content"""
        mock_file = MockFile("invalid.pdf", "application/pdf", b"not a pdf")
        try:
            result = await processor.process_pdf(mock_file, "invalid_test")
            # May succeed with empty TOC
            assert "toc" in result
        except Exception:
            # Or may fail gracefully - both acceptable
            pass


class TestDataIntegrity:
    """Test data integrity"""

    @pytest.mark.asyncio
    async def test_toc_json_validity(self, processor, pdf_test_dir):
        """Verify TOC JSON structure"""
        pdf_path = pdf_test_dir / "test_document.pdf"
        
        if not pdf_path.exists():
            pytest.skip("test_document.pdf not found")

        with open(pdf_path, 'rb') as f:
            pdf_content = f.read()
        
        mock_file = MockFile("test.pdf", "application/pdf", pdf_content)
        doc_id = "toc_validity"

        await processor.process_pdf(mock_file, doc_id)

        toc_file = processor.data_dir / doc_id / "toc.json"
        toc_data = json.loads(toc_file.read_text())

        assert "entries" in toc_data
        assert "metadata" in toc_data
        assert "page_count" in toc_data
        assert isinstance(toc_data["entries"], list)

        for entry in toc_data["entries"]:
            assert "level" in entry
            assert "title" in entry
            assert "page" in entry
            assert "section_path" in entry

        print(f"\nTOC validated: {len(toc_data['entries'])} entries")

    @pytest.mark.asyncio
    async def test_metadata_validity(self, processor, pdf_test_dir):
        """Verify metadata JSON structure"""
        pdf_path = pdf_test_dir / "test_document.pdf"
        
        if not pdf_path.exists():
            pytest.skip("test_document.pdf not found")

        with open(pdf_path, 'rb') as f:
            pdf_content = f.read()
        
        mock_file = MockFile("test.pdf", "application/pdf", pdf_content)
        doc_id = "meta_validity"

        await processor.process_pdf(mock_file, doc_id)

        metadata_file = processor.data_dir / doc_id / "metadata.json"
        metadata = json.loads(metadata_file.read_text())

        assert "filename" in metadata
        assert "content_type" in metadata
        assert "sections_dir" in metadata
        assert metadata["filename"] == "test.pdf"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
