"""High coverage tests using real test PDF files to achieve 90%+ coverage"""
import pytest
import asyncio
import json
import tempfile
from pathlib import Path
import sys
import time

sys.path.insert(0, '/home/wilson/opencode/hkex-ipo-sentinel-python')
from pdf_processor.core.pdf_processor_final import (
    PDFProcessorChunks,
    SectionChunkStrategy
)


class MockFile:
    """Mock UploadFile for testing"""
    def __init__(self, filename, content_type, content):
        self.filename = filename
        self.content_type = content_type
        self._content = content
    async def read(self):
        return self._content


@pytest.fixture
def test_pdf():
    """Get path to test PDF file"""
    return Path("/home/wilson/opencode/hkex-ipo-sentinel-python/data/pdf/test_document.pdf")


class TestPDFProcessorChunksCoverage:
    """Coverage tests for all code paths"""
    
    def test_init_coverage(self):
        """Test all initialization code paths"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Test default initialization
            processor1 = PDFProcessorChunks(data_dir=tmpdir)
            assert processor1.strategy == SectionChunkStrategy.BY_PAGES
            
            # Test with custom parameters
            processor2 = PDFProcessorChunks(
                data_dir=tmpdir,
                strategy=SectionChunkStrategy.BY_TOC_CHUNKED,
                pages_per_chunk=20,
                max_section_size=40
            )
            assert processor2.pages_per_chunk == 20
            assert processor2.max_section_size == 40
    
    @pytest.mark.asyncio
    async def test_process_pdf_all_strategies(self, test_pdf):
        """Test process_pdf with all strategies"""
        if not test_pdf.exists():
            pytest.skip("test_document.pdf not found")
        
        strategies = [
            SectionChunkStrategy.BY_PAGES,
            SectionChunkStrategy.BY_TOC_CHUNKED,
            SectionChunkStrategy.BY_TOC,
        ]
        
        for strategy in strategies:
            with tempfile.TemporaryDirectory() as tmpdir:
                processor = PDFProcessorChunks(
                    data_dir=tmpdir,
                    strategy=strategy,
                    pages_per_chunk=10
                )
                
                with open(test_pdf, 'rb') as f:
                    pdf_content = f.read()
                
                mock_file = MockFile("test.pdf", "application/pdf", pdf_content)
                result = await processor.process_pdf(mock_file, f"test_{strategy}")
                
                assert "toc" in result
                assert "metadata" in result
                assert result["metadata"]["strategy"] == strategy.value
                assert result["toc"] is not None
    
    @pytest.mark.asyncio
    async def test_page_chunks_coverage(self, test_pdf):
        """Test BY_PAGES strategy with different chunk sizes"""
        if not test_pdf.exists():
            pytest.skip("test_document.pdf not found")
        
        chunk_sizes = [5, 10, 20]
        
        for chunk_size in chunk_sizes:
            with tempfile.TemporaryDirectory() as tmpdir:
                processor = PDFProcessorChunks(
                    data_dir=tmpdir,
                    strategy=SectionChunkStrategy.BY_PAGES,
                    pages_per_chunk=chunk_size
                )
                
                with open(test_pdf, 'rb') as f:
                    pdf_content = f.read()
                
                mock_file = MockFile("test.pdf", "application/pdf", pdf_content)
                result = await processor.process_pdf(mock_file, f"pages_{chunk_size}")
                
                assert len(result["toc"]) > 0
                doc_dir = processor.data_dir / f"pages_{chunk_size}"
                sections_dir = doc_dir / "sections"
                section_count = len(list(sections_dir.glob("*.md")))
                assert section_count == len(result["toc"])
    
    @pytest.mark.asyncio
    async def test_toc_chunked_coverage(self, test_pdf):
        """Test BY_TOC_CHUNKED strategy variations"""
        if not test_pdf.exists():
            pytest.skip("test_document.pdf not found")
        
        for max_size in [1, 2, 5, 10]:
            with tempfile.TemporaryDirectory() as tmpdir:
                processor = PDFProcessorChunks(
                    data_dir=tmpdir,
                    strategy=SectionChunkStrategy.BY_TOC_CHUNKED,
                    max_section_size=max_size
                )
                
                with open(test_pdf, 'rb') as f:
                    pdf_content = f.read()
                
                mock_file = MockFile("test.pdf", "application/pdf", pdf_content)
                result = await processor.process_pdf(mock_file, f"chunked_{max_size}")
                
                assert result["toc"] is not None
    
    def test_clean_title_coverage(self):
        """Test _clean_title with various inputs"""
        with tempfile.TemporaryDirectory() as tmpdir:
            processor = PDFProcessorChunks(data_dir=tmpdir)
            
            # Test cases
            test_cases = [
                ("Simple Title", "Simple Title"),
                ("Title: with - and _", "Title with  and _"),
                ("   lots   of   spaces   ", "lots   of   spaces"),
                ("Special@#Characters$", "SpecialCharacters"),
                ("A" * 100, "A" * 50),  # Length truncation
                ("", ""),  # Empty string
                ("123", "123"),  # Numbers only
                ("Mixed123Title", "Mixed123Title"),
            ]
            
            for input_title, expected_part in test_cases:
                result = processor._clean_title(input_title)
                if input_title:
                    assert len(result) <= 50
                    assert "@" not in result
                    assert "#" not in result
    
    def test_find_toc_entries_coverage(self):
        """Test _find_toc_entries_for_pages with various scenarios"""
        with tempfile.TemporaryDirectory() as tmpdir:
            processor = PDFProcessorChunks(data_dir=tmpdir)
            
            # Test with various TOC structures
            test_cases = [
                # (toc, pages, expected_min_results)
                ([], [0, 1], 0),  # Empty TOC
                ([(1, "Chapter 1", 1)], [0], 1),  # Single entry, single page
                ([(1, "Chapter 1", 1), (2, "Section 1", 2)], [0, 1], 2),  # Multiple entries
                ([(1, "Chapter 1", 5)], [0, 1], 1),  # TOC not in page range
            ]
            
            for toc, pages, expected_min in test_cases:
                result = processor._find_toc_entries_for_pages(toc, pages)
                assert len(result) >= expected_min
    
    @pytest.mark.asyncio
    async def test_extract_chunk_content_coverage(self):
        """Test _extract_chunk_content with various scenarios"""
        with tempfile.TemporaryDirectory() as tmpdir:
            processor = PDFProcessorChunks(data_dir=tmpdir)
            
            # Use a small test PDF
            test_pdf = Path("/home/wilson/opencode/hkex-ipo-sentinel-python/data/pdf/test_document.pdf")
            
            if test_pdf.exists():
                # Test single page
                content1 = await processor._extract_chunk_content(str(test_pdf), [0])
                assert isinstance(content1, str)
                
                # Test multiple pages
                content2 = await processor._extract_chunk_content(str(test_pdf), [0, 1, 2])
                assert isinstance(content2, str)
                assert len(content2) >= len(content1)
                
                # Test with non-existent pages (should handle gracefully)
                content3 = await processor._extract_chunk_content(str(test_pdf), [9999])
                assert isinstance(content3, str)
    
    @pytest.mark.asyncio
    async def test_chunk_large_section_coverage(self):
        """Test _chunk_large_section with different scenarios"""
        with tempfile.TemporaryDirectory() as tmpdir:
            processor = PDFProcessorChunks(data_dir=tmpdir, pages_per_chunk=3)
            
            test_pdf = Path("/home/wilson/opencode/hkex-ipo-sentinel-python/data/pdf/test_document.pdf")
            
            if test_pdf.exists():
                with patch('pdf_processor.core.pdf_processor_final.PDFProcessorChunks._extract_chunk_content') as mock_extract:
                    mock_extract.return_value = "# Test Content"
                    
                    sections_dir = Path(tmpdir) / "test" / "sections"
                    sections_dir.mkdir(parents=True)
                    
                    # Test small section
                    pages_small = list(range(2))
                    result1, counter1 = await processor._chunk_large_section(
                        str(test_pdf), sections_dir, pages_small, 1, "Small Section", 0
                    )
                    assert len(result1) == 1
                    
                    # Test large section
                    pages_large = list(range(10))
                    result2, counter2 = await processor._chunk_large_section(
                        str(test_pdf), sections_dir, pages_large, 1, "Large Section", 0
                    )
                    assert len(result2) > 1
    
    def test_get_section_content_coverage(self):
        """Test get_section_content with various scenarios"""
        with tempfile.TemporaryDirectory() as tmpdir:
            processor = PDFProcessorChunks(data_dir=tmpdir)
            
            doc_dir = Path(tmpdir) / "test_doc"
            sections_dir = doc_dir / "sections"
            sections_dir.mkdir(parents=True)
            
            # Create test section files
            test_sections = [
                ("section_001_test.md", "# Content 1"),
                ("section_002_empty.md", ""),
                ("section_003_long.md", "A" * 10000),
            ]
            
            for filename, content in test_sections:
                (sections_dir / filename).write_text(content)
            
            # Test retrieval
            content1 = processor.get_section_content("test_doc", "section_001_test")
            assert content1 == "# Content 1"
            
            content2 = processor.get_section_content("test_doc", "section_002_empty")
            assert content2 == ""
            
            content3 = processor.get_section_content("test_doc", "section_003_long")
            assert len(content3) == 10000
            
            # Test non-existent section
            with pytest.raises(FileNotFoundError):
                processor.get_section_content("test_doc", "section_000_nonexistent")
    
    def test_get_document_toc_coverage(self):
        """Test get_document_toc with various scenarios"""
        with tempfile.TemporaryDirectory() as tmpdir:
            processor = PDFProcessorChunks(data_dir=tmpdir)
            
            # Create TOC file
            doc_dir = Path(tmpdir) / "test_doc"
            doc_dir.mkdir(parents=True)
            
            # Test with valid TOC
            toc_file = doc_dir / "toc.json"
            toc_data = {
                "entries": [
                    {"level": 1, "title": "Test", "page": 1, "section_path": "sec1"},
                    {"level": 2, "title": "Section", "page": 2, "section_path": "sec2"},
                ],
                "metadata": {"title": "Test Doc"},
                "page_count": 10
            }
            toc_file.write_text(json.dumps(toc_data))
            
            result = processor.get_document_toc("test_doc")
            assert "entries" in result
            assert "metadata" in result
            assert "page_count" in result
            assert len(result["entries"]) == 2
            
            # Test with non-existent document
            with pytest.raises(FileNotFoundError):
                processor.get_document_toc("nonexistent")
            
            # Test with valid TOC with extra fields
            toc_data_with_extra = {
                "entries": [{"level": 1, "title": "Test", "page": 1, "section_path": "sec1", "extra": "field"}],
                "metadata": {},
                "page_count": 5,
                "extra_field": "value"
            }
            toc_file.write_text(json.dumps(toc_data_with_extra))
            
            result_extra = processor.get_document_toc("test_doc")
            assert "extra_field" in result_extra
    
    @pytest.mark.asyncio
    async def test_process_pdf_metadata_coverage(self, test_pdf):
        """Test metadata handling in process_pdf"""
        if not test_pdf.exists():
            pytest.skip("test_document.pdf not found")
        
        with tempfile.TemporaryDirectory() as tmpdir:
            processor = PDFProcessorChunks(data_dir=tmpdir)
            
            with open(test_pdf, 'rb') as f:
                pdf_content = f.read()
            
            test_files = [
                ("test.pdf", "application/pdf"),
                ("document.pdf", "application/pdf"),
                ("file with spaces.pdf", "application/pdf"),
            ]
            
            for filename, content_type in test_files:
                mock_file = MockFile(filename, content_type, pdf_content)
                result = await processor.process_pdf(mock_file, f"meta_{filename.replace(' ', '_')}")
                
                assert result["metadata"]["filename"] == filename
                assert result["metadata"]["content_type"] == content_type
                assert "sections_dir" in result["metadata"]
                assert "strategy" in result["metadata"]
                assert "total_pages" in result["metadata"]
    
    @pytest.mark.asyncio
    async def test_error_handling_coverage(self, test_pdf):
        """Test error handling scenarios"""
        if not test_pdf.exists():
            pytest.skip("test_document.pdf not found")
        
        with tempfile.TemporaryDirectory() as tmpdir:
            processor = PDFProcessorChunks(data_dir=tmpdir)
            
            # Test retrieving non-existent section
            with pytest.raises(FileNotFoundError):
                processor.get_section_content("nonexistent_doc", "nonexistent_section")
            
            # Test retrieving non-existent TOC
            with pytest.raises(FileNotFoundError):
                processor.get_document_toc("nonexistent_doc")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=pdf_processor.core.pdf_processor_final", "--cov-report=html", "--cov-report=term-missing"])
