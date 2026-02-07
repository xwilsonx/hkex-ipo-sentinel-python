#!/usr/bin/env python3
"""Test all SEHK PDF files individually with appropriate timeouts"""

import pytest
import asyncio
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, '/home/wilson/opencode/hkex-ipo-sentinel-python')
from pdf_processor.core.pdf_processor import PDFProcessor


class MockFile:
    def __init__(self, filename, content_type, content):
        self.filename = filename
        self.content_type = content_type
        self._content = content
    async def read(self):
        return self._content


@pytest.fixture
def processor():
    from tempfile import TemporaryDirectory
    with TemporaryDirectory() as tmpdir:
        yield PDFProcessor(data_dir=tmpdir)


@pytest.fixture
def sehk_files():
    """Get all SEHK PDF files"""
    pdf_dir = Path("/home/wilson/opencode/hkex-ipo-sentinel-python/data/pdf")
    return {
        "sehk26020600999": pdf_dir / "sehk26020600999.pdf",
        "sehk26020600953": pdf_dir / "sehk26020600953.pdf",
        "sehk26012600719": pdf_dir / "sehk26012600719.pdf",
        "sehk26013000306": pdf_dir / "sehk26013000306.pdf",
        "sehk26012601375": pdf_dir / "sehk26012601375.pdf",
    }


class TestSEHKFiles:
    """Test all SEHK PDF files comprehensively"""

    @pytest.mark.timeout(30)
    @pytest.mark.asyncio
    async def test_sehk26020600999_smallest(self, processor, sehk_files):
        """Test smallest SEHK file (53KB)"""
        pdf_path = sehk_files["sehk26020600999"]
        if not pdf_path.exists():
            pytest.skip("File not found")

        print(f"\nTesting {pdf_path.name} ({pdf_path.stat().st_size / 1024:.1f} KB)")
        
        with open(pdf_path, 'rb') as f:
            pdf_content = f.read()
        
        mock_file = MockFile(pdf_path.name, "application/pdf", pdf_content)
        doc_id = "sehk26020600999"

        result = await processor.process_pdf(mock_file, doc_id)

        assert "toc" in result
        assert "metadata" in result
        assert isinstance(result["toc"], list)

        print(f"  TOC entries: {len(result['toc'])}")
        print(f"  Status: ✓ SUCCESS (no TOC expected)")

    @pytest.mark.timeout(30)
    @pytest.mark.asyncio
    async def test_sehk26020600953_medium_no_toc(self, processor, sehk_files):
        """Test medium SEHK file without TOC (183KB)"""
        pdf_path = sehk_files["sehk26020600953"]
        if not pdf_path.exists():
            pytest.skip("File not found")

        print(f"\nTesting {pdf_path.name} ({pdf_path.stat().st_size / 1024:.1f} KB)")
        
        with open(pdf_path, 'rb') as f:
            pdf_content = f.read()
        
        mock_file = MockFile(pdf_path.name, "application/pdf", pdf_content)
        doc_id = "sehk26020600953"

        result = await processor.process_pdf(mock_file, doc_id)

        assert "toc" in result
        assert "metadata" in result

        print(f"  TOC entries: {len(result['toc'])}")
        print(f"  Status: ✓ SUCCESS")

    @pytest.mark.timeout(180)
    @pytest.mark.asyncio
    async def test_sehk26012600719_large_with_toc(self, processor, sehk_files):
        """Test large SEHK file with TOC (3.2MB)"""
        pdf_path = sehk_files["sehk26012600719"]
        if not pdf_path.exists():
            pytest.skip("File not found")

        print(f"\nTesting {pdf_path.name} ({pdf_path.stat().st_size / 1024:.1f} KB)")
        
        start_time = time.time()
        with open(pdf_path, 'rb') as f:
            pdf_content = f.read()
        
        mock_file = MockFile(pdf_path.name, "application/pdf", pdf_content)
        doc_id = "sehk26012600719"

        result = await processor.process_pdf(mock_file, doc_id)
        elapsed = time.time() - start_time

        assert "toc" in result
        assert "metadata" in result
        assert len(result["toc"]) > 0

        print(f"  TOC entries: {len(result['toc'])}")
        print(f"  Processing time: {elapsed:.1f}s")
        
        # Verify TOC structure
        toc_file = processor.data_dir / doc_id / "toc.json"
        assert toc_file.exists()
        toc_data = json.loads(toc_file.read_text())
        assert len(toc_data["entries"]) > 0

        print(f"  First entry: {toc_data['entries'][0]['title']}")
        print(f"  Last entry: {toc_data['entries'][-1]['title'][:50]}...")
        print(f"  Status: ✓ SUCCESS")

    @pytest.mark.timeout(180)
    @pytest.mark.asyncio
    async def test_sehk26013000306_large_with_toc(self, processor, sehk_files):
        """Test large SEHK file with TOC (4.8MB)"""
        pdf_path = sehk_files["sehk26013000306"]
        if not pdf_path.exists():
            pytest.skip("File not found")

        print(f"\nTesting {pdf_path.name} ({pdf_path.stat().st_size / 1024:.1f} KB)")
        
        start_time = time.time()
        with open(pdf_path, 'rb') as f:
            pdf_content = f.read()
        
        mock_file = MockFile(pdf_path.name, "application/pdf", pdf_content)
        doc_id = "sehk26013000306"

        result = await processor.process_pdf(mock_file, doc_id)
        elapsed = time.time() - start_time

        assert "toc" in result
        assert "metadata" in result
        assert len(result["toc"]) > 0

        print(f"  TOC entries: {len(result['toc'])}")
        print(f"  Processing time: {elapsed:.1f}s")
        
        toc_file = processor.data_dir / doc_id / "toc.json"
        toc_data = json.loads(toc_file.read_text())
        
        print(f"  First entry: {toc_data['entries'][0]['title']}")
        print(f"  Last entry: {toc_data['entries'][-1]['title'][:50]}...")
        print(f"  Status: ✓ SUCCESS")

    @pytest.mark.timeout(180)
    @pytest.mark.asyncio
    async def test_sehk26012601375_largest(self, processor, sehk_files):
        """Test largest SEHK file with TOC (9.4MB)"""
        pdf_path = sehk_files["sehk26012601375"]
        if not pdf_path.exists():
            pytest.skip("File not found")

        print(f"\nTesting {pdf_path.name} ({pdf_path.stat().st_size / 1024:.1f} KB)")
        
        start_time = time.time()
        with open(pdf_path, 'rb') as f:
            pdf_content = f.read()
        
        mock_file = MockFile(pdf_path.name, "application/pdf", pdf_content)
        doc_id = "sehk26012601375"

        result = await processor.process_pdf(mock_file, doc_id)
        elapsed = time.time() - start_time

        assert "toc" in result
        assert "metadata" in result
        assert len(result["toc"]) > 0

        print(f"  TOC entries: {len(result['toc'])}")
        print(f"  Processing time: {elapsed:.1f}s")
        
        toc_file = processor.data_dir / doc_id / "toc.json"
        toc_data = json.loads(toc_file.read_text())
        
        print(f"  First entry: {toc_data['entries'][0]['title']}")
        print(f"  Last entry: {toc_data['entries'][-1]['title'][:50]}...")
        print(f"  Status: ✓ SUCCESS")


class TestSEHKContent:
    """Test content retrieval from SEHK files"""

    @pytest.mark.timeout(60)
    @pytest.mark.asyncio
    async def test_sehk_sections_access(self, processor, sehk_files):
        """Test accessing sections from SEHK file with TOC"""
        pdf_path = sehk_files["sehk26013000306"]
        if not pdf_path.exists():
            pytest.skip("File not found")

        print(f"\nTesting section access for {pdf_path.name}")
        
        with open(pdf_path, 'rb') as f:
            pdf_content = f.read()
        
        mock_file = MockFile(pdf_path.name, "application/pdf", pdf_content)
        doc_id = "sehk_sections_test"

        result = await processor.process_pdf(mock_file, doc_id)
        
        # Test retrieving first 3 sections
        for i, entry in enumerate(result["toc"][:3]):
            section_path = entry["section_path"]
            content = processor.get_section_content(doc_id, section_path)
            assert isinstance(content, str)
            assert len(content) > 0
            print(f"  Section {i}: {entry['title'][:30]}... ({len(content)} chars)")

        print(f"  Status: ✓ All sections accessible")

    @pytest.mark.timeout(60)
    @pytest.mark.asyncio
    async def test_sehk_toc_validation(self, processor, sehk_files):
        """Validate TOC structure for SEHK files"""
        pdf_path = sehk_files["sehk26012600719"]
        if not pdf_path.exists():
            pytest.skip("File not found")

        print(f"\nTesting TOC validation for {pdf_path.name}")
        
        with open(pdf_path, 'rb') as f:
            pdf_content = f.read()
        
        mock_file = MockFile(pdf_path.name, "application/pdf", pdf_content)
        doc_id = "sehk_toc_validation"

        await processor.process_pdf(mock_file, doc_id)

        toc_file = processor.data_dir / doc_id / "toc.json"
        toc_data = json.loads(toc_file.read_text())

        # Validate structure
        assert "entries" in toc_data
        assert "metadata" in toc_data
        assert "page_count" in toc_data

        # Validate each entry
        for entry in toc_data["entries"][:5]:
            assert "level" in entry
            assert "title" in entry
            assert "page" in entry
            assert "section_path" in entry
            assert entry["level"] > 0
            assert entry["page"] > 0

        print(f"  Total entries: {len(toc_data['entries'])}")
        print(f"  Page count: {toc_data['page_count']}")
        print(f"  Status: ✓ TOC structure valid")


class TestSEHKErrorHandling:
    """Test error handling with SEHK files"""

    @pytest.mark.timeout(30)
    @pytest.mark.asyncio
    async def test_sehk_empty_section_retrieval(self, processor):
        """Test retrieving non-existent section"""
        with pytest.raises(FileNotFoundError):
            processor.get_section_content("nonexistent_doc", "nonexistent_section")

    @pytest.mark.timeout(30)
    @pytest.mark.asyncio
    async def test_sehk_nonexistent_document_toc(self, processor):
        """Test getting TOC for non-existent document"""
        with pytest.raises(FileNotFoundError):
            processor.get_document_toc("nonexistent_sehk_doc")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
