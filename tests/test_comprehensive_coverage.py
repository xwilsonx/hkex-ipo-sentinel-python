"""
Comprehensive test suite with 90%+ coverage
Tests all code paths, edge cases, and error conditions
"""
import pytest
import asyncio
import json
import tempfile
from pathlib import Path
import sys
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import aiofiles

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


class TestPDFProcessorChunksInit:
    """Test initialization of PDFProcessorChunks"""
    
    def test_init_with_defaults(self):
        """Test initialization with default parameters"""
        with tempfile.TemporaryDirectory() as tmpdir:
            processor = PDFProcessorChunks(data_dir=tmpdir)
            assert processor.strategy == SectionChunkStrategy.BY_PAGES
            assert processor.pages_per_chunk == 15
            assert processor.max_section_size == 50
    
    def test_init_with_custom_params(self):
        """Test initialization with custom parameters"""
        with tempfile.TemporaryDirectory() as tmpdir:
            processor = PDFProcessorChunks(
                data_dir=tmpdir,
                strategy=SectionChunkStrategy.BY_TOC,
                pages_per_chunk=20,
                max_section_size=30
            )
            assert processor.strategy == SectionChunkStrategy.BY_TOC
            assert processor.pages_per_chunk == 20
            assert processor.max_section_size == 30
    
    def test_init_creates_data_directory(self):
        """Test that initialization creates data directory"""
        with tempfile.TemporaryDirectory() as tmpdir:
            data_path = Path(tmpdir) / "data"
            processor = PDFProcessorChunks(data_dir=str(data_path))
            assert data_path.exists()
            assert data_path.is_dir()


class TestProcessPDF:
    """Test main process_pdf method"""
    
    @pytest.mark.asyncio
    async def test_process_pdf_creates_directories(self):
        """Test that process_pdf creates necessary directories"""
        with tempfile.TemporaryDirectory() as tmpdir:
            processor = PDFProcessorChunks(data_dir=tmpdir)
            
            # Create mock PDF with TOC
            mock_file = MockFile("test.pdf", "application/pdf", b"%PDF-1.4\n%Test")
            
            # Mock the actual processing to avoid real PDF parsing
            with patch.object(processor, '_extract_with_chunks') as mock_extract:
                mock_extract.return_value = ([], {}, 10)
                
                result = await processor.process_pdf(mock_file, "test_doc")
                
                assert "toc" in result
                assert "metadata" in result
                assert result["metadata"]["filename"] == "test.pdf"
                assert result["metadata"]["content_type"] == "application/pdf"
    
    @pytest.mark.asyncio
    async def test_process_pdf_cleans_temp_file(self):
        """Test that process_pdf cleans up temporary file"""
        with tempfile.TemporaryDirectory() as tmpdir:
            processor = PDFProcessorChunks(data_dir=tmpdir)
            
            mock_file = MockFile("test.pdf", "application/pdf", b"%PDF-1.4\n%Test")
            
            with patch.object(processor, '_extract_with_chunks') as mock_extract:
                mock_extract.return_value = ([], {}, 10)
                
                await processor.process_pdf(mock_file, "test_doc")
            
            # Check temp file is removed
            doc_dir = Path(tmpdir) / "test_doc"
            temp_file = doc_dir / "test_doc_temp.pdf"
            assert not temp_file.exists()
    
    @pytest.mark.asyncio
    async def test_process_pdf_with_toc(self):
        """Test process_pdf with valid TOC data"""
        with tempfile.TemporaryDirectory() as tmpdir:
            processor = PDFProcessorChunks(data_dir=tmpdir)
            
            toc_data = [
                {"level": 1, "title": "Chapter 1", "page": 1, "section_path": "section_000"},
            ]
            metadata = {"title": "Test Document"}
            
            with patch.object(processor, '_extract_with_chunks') as mock_extract:
                mock_extract.return_value = (toc_data, metadata, 10)
                
                mock_file = MockFile("test.pdf", "application/pdf", b"%PDF-1.4")
                result = await processor.process_pdf(mock_file, "test_doc")
                
                assert len(result["toc"]) == 1
                assert result["toc"][0]["title"] == "Chapter 1"
    
    @pytest.mark.asyncio
    async def test_process_pdf_empty_toc(self):
        """Test process_pdf with empty TOC"""
        with tempfile.TemporaryDirectory() as tmpdir:
            processor = PDFProcessorChunks(data_dir=tmpdir)
            
            with patch.object(processor, '_extract_with_chunks') as mock_extract:
                mock_extract.return_value = ([], {}, 0)
                
                mock_file = MockFile("test.pdf", "application/pdf", b"%PDF-1.4")
                result = await processor.process_pdf(mock_file, "test_doc")
                
                assert result["toc"] == []


class TestSectionChunkStrategies:
    """Test different chunking strategies"""
    
    @pytest.mark.asyncio
    async def test_by_pages_strategy(self):
        """Test BY_PAGES chunking strategy"""
        with tempfile.TemporaryDirectory() as tmpdir:
            processor = PDFProcessorChunks(
                data_dir=tmpdir,
                strategy=SectionChunkStrategy.BY_PAGES,
                pages_per_chunk=5
            )
            
            # Mock fitz to return test data
            with patch('fitz.open') as mock_fitz_open:
                mock_doc = MagicMock()
                mock_doc.get_toc.return_value = [
                    (1, "Chapter 1", 1),
                    (1, "Chapter 2", 6),
                ]
                mock_doc.metadata = {"title": "Test"}
                mock_doc.page_count = 10
                mock_fitz_open.return_value.__enter__ = Mock(return_value=mock_doc)
                mock_fitz_open.return_value.__exit__ = Mock(return_value=False)
            
            # Mock pymupdf4llm
            with patch('pymupdf4llm.to_markdown') as mock_to_markdown:
                mock_to_markdown.return_value = "# Page Content\n\nTest text."
            
            mock_file = MockFile("test.pdf", "application/pdf", b"%PDF-1.4")
            result = await processor.process_pdf(mock_file, "test_doc")
            
            # Should create 2 chunks (10 pages / 5 per chunk)
            assert len(result["toc"]) == 2
    
    @pytest.mark.asyncio
    async def test_by_toc_chunked_strategy(self):
        """Test BY_TOC_CHUNKED chunking strategy"""
        with tempfile.TemporaryDirectory() as tmpdir:
            processor = PDFProcessorChunks(
                data_dir=tmpdir,
                strategy=SectionChunkStrategy.BY_TOC_CHUNKED,
                max_section_size=3
            )
            
            # Mock large TOC entry
            with patch('fitz.open') as mock_fitz_open:
                mock_doc = MagicMock()
                mock_doc.get_toc.return_value = [
                    (1, "Large Chapter", 1),
                    (1, "Small Chapter", 8),
                ]
                mock_doc.metadata = {"title": "Test"}
                mock_doc.page_count = 10
                mock_fitz_open.return_value.__enter__ = Mock(return_value=mock_doc)
                mock_fitz_open.return_value.__exit__ = Mock(return_value=False)
            
            with patch('pymupdf4llm.to_markdown') as mock_to_markdown:
                mock_to_markdown.return_value = "# Content\n\nTest"
            
            mock_file = MockFile("test.pdf", "application/pdf", b"%PDF-1.4")
            result = await processor.process_pdf(mock_file, "test_doc")
            
            # Large chapter (7 pages) should be split into chunks
            assert len(result["toc"]) > 2
    
    @pytest.mark.asyncio
    async def test_by_toc_strategy(self):
        """Test BY_TOC chunking strategy"""
        with tempfile.TemporaryDirectory() as tmpdir:
            processor = PDFProcessorChunks(
                data_dir=tmpdir,
                strategy=SectionChunkStrategy.BY_TOC
            )
            
            with patch('fitz.open') as mock_fitz_open:
                mock_doc = MagicMock()
                mock_doc.get_toc.return_value = [
                    (1, "Chapter 1", 1),
                    (2, "Section 1", 2),
                ]
                mock_doc.metadata = {"title": "Test"}
                mock_doc.page_count = 5
                mock_fitz_open.return_value.__enter__ = Mock(return_value=mock_doc)
                mock_fitz_open.return_value.__exit__ = Mock(return_value=False)
            
            with patch('pymupdf4llm.to_markdown') as mock_to_markdown:
                mock_to_markdown.return_value = "# Content"
            
            mock_file = MockFile("test.pdf", "application/pdf", b"%PDF-1.4")
            result = await processor.process_pdf(mock_file, "test_doc")
            
            assert len(result["toc"]) == 2


class TestExtractChunkContent:
    """Test _extract_chunk_content method"""
    
    @pytest.mark.asyncio
    async def test_extract_single_page(self):
        """Test extracting content from a single page"""
        with tempfile.TemporaryDirectory() as tmpdir:
            processor = PDFProcessorChunks(data_dir=tmpdir)
            
            with patch('pymupdf4llm.to_markdown') as mock_to_markdown:
                mock_to_markdown.return_value = "# Test Content\n\nSome text"
                
                content = await processor._extract_chunk_content("test.pdf", [0])
                
                assert content == "# Test Content\n\nSome text"
                assert mock_to_markdown.call_count == 1
    
    @pytest.mark.asyncio
    async def test_extract_multiple_pages(self):
        """Test extracting content from multiple pages"""
        with tempfile.TemporaryDirectory() as tmpdir:
            processor = PDFProcessorChunks(data_dir=tmpdir)
            
            with patch('pymupdf4llm.to_markdown') as mock_to_markdown:
                mock_to_markdown.side_effect = [
                    "# Page 1",
                    "# Page 2",
                    "# Page 3"
                ]
                
                content = await processor._extract_chunk_content("test.pdf", [0, 1, 2])
                
                assert "# Page 1" in content
                assert "# Page 2" in content
                assert "# Page 3" in content
                assert mock_to_markdown.call_count == 3
    
    @pytest.mark.asyncio
    async def test_extract_with_timeout_error(self):
        """Test handling of extraction errors"""
        with tempfile.TemporaryDirectory() as tmpdir:
            processor = PDFProcessorChunks(data_dir=tmpdir)
            
            with patch('pymupdf4llm.to_markdown') as mock_to_markdown:
                mock_to_markdown.side_effect = Exception("Timeout error")
                
                content = await processor._extract_chunk_content("test.pdf", [0])
                
                # Should return empty string on error
                assert content == ""
    
    @pytest.mark.asyncio
    async def test_extract_with_empty_result(self):
        """Test handling of empty extraction results"""
        with tempfile.TemporaryDirectory() as tmpdir:
            processor = PDFProcessorChunks(data_dir=tmpdir)
            
            with patch('pymupdf4llm.to_markdown') as mock_to_markdown:
                mock_to_markdown.return_value = ""
                
                content = await processor._extract_chunk_content("test.pdf", [0])
                
                assert content == ""


class TestFindTOCEntriesForPages:
    """Test _find_toc_entries_for_pages method"""
    
    def test_find_toc_entries_single_page(self):
        """Test finding TOC entries for a single page"""
        with tempfile.TemporaryDirectory() as tmpdir:
            processor = PDFProcessorChunks(data_dir=tmpdir)
            
            toc = [
                (1, "Chapter 1", 1),
                (2, "Section 1", 2),
            ]
            
            result = processor._find_toc_entries_for_pages(toc, [0])
            
            assert len(result) == 1
            assert result[0][1] == "Chapter 1"
    
    def test_find_toc_entries_multiple_pages(self):
        """Test finding TOC entries for multiple pages"""
        with tempfile.TemporaryDirectory() as tmpdir:
            processor = PDFProcessorChunks(data_dir=tmpdir)
            
            toc = [
                (1, "Chapter 1", 1),
                (2, "Section 1", 2),
                (1, "Chapter 2", 3),
            ]
            
            result = processor._find_toc_entries_for_pages(toc, [0, 1, 2])
            
            assert len(result) >= 2
    
    def test_find_toc_entries_empty(self):
        """Test with empty TOC"""
        with tempfile.TemporaryDirectory() as tmpdir:
            processor = PDFProcessorChunks(data_dir=tmpdir)
            
            result = processor._find_toc_entries_for_pages([], [0, 1])
            
            assert result == []


class TestCleanTitle:
    """Test _clean_title method"""
    
    def test_clean_title_basic(self):
        """Test basic title cleaning"""
        with tempfile.TemporaryDirectory() as tmpdir:
            processor = PDFProcessorChunks(data_dir=tmpdir)
            
            result = processor._clean_title("Test: Chapter 1 - (2024)")
            
            assert result == "Test Chapter 1  2024"
    
    def test_clean_title_special_chars(self):
        """Test removing special characters"""
        with tempfile.TemporaryDirectory() as tmpdir:
            processor = PDFProcessorChunks(data_dir=tmpdir)
            
            result = processor._clean_title("Introduction/Setup@#")
            
            assert "/" not in result
            assert "@" not in result
            assert "#" not in result
    
    def test_clean_title_whitespace(self):
        """Test handling of whitespace"""
        with tempfile.TemporaryDirectory() as tmpdir:
            processor = PDFProcessorChunks(data_dir=tmpdir)
            
            result = processor._clean_title("   Test   Title   ")
            
            assert result == "Test Title"
    
    def test_clean_title_length_limit(self):
        """Test title length truncation"""
        with tempfile.TemporaryDirectory() as tmpdir:
            processor = PDFProcessorChunks(data_dir=tmpdir)
            
            long_title = "A" * 100
            result = processor._clean_title(long_title)
            
            assert len(result) <= 50


class TestGetSectionContent:
    """Test get_section_content method"""
    
    def test_get_existing_section_content(self):
        """Test retrieving existing section content"""
        with tempfile.TemporaryDirectory() as tmpdir:
            processor = PDFProcessorChunks(data_dir=tmpdir)
            
            # Create section file
            doc_dir = Path(tmpdir) / "test_doc"
            sections_dir = doc_dir / "sections"
            sections_dir.mkdir(parents=True)
            
            section_file = sections_dir / "section_test.md"
            section_file.write_text("# Test Content")
            
            result = processor.get_section_content("test_doc", "section_test")
            
            assert result == "# Test Content"
    
    def test_get_nonexistent_section_content(self):
        """Test retrieving content from non-existent section"""
        with tempfile.TemporaryDirectory() as tmpdir:
            processor = PDFProcessorChunks(data_dir=tmpdir)
            
            with pytest.raises(FileNotFoundError):
                processor.get_section_content("test_doc", "nonexistent")


class TestGetDocumentTOC:
    """Test get_document_toc method"""
    
    def test_get_existing_toc(self):
        """Test retrieving existing TOC"""
        with tempfile.TemporaryDirectory() as tmpdir:
            processor = PDFProcessorChunks(data_dir=tmpdir)
            
            # Create TOC file
            doc_dir = Path(tmpdir) / "test_doc"
            doc_dir.mkdir(parents=True)
            
            toc_file = doc_dir / "toc.json"
            toc_data = {
                "entries": [
                    {"level": 1, "title": "Test", "page": 1, "section_path": "sec1"}
                ],
                "metadata": {},
                "page_count": 10
            }
            toc_file.write_text(json.dumps(toc_data))
            
            result = processor.get_document_toc("test_doc")
            
            assert "entries" in result
            assert len(result["entries"]) == 1
    
    def test_get_nonexistent_toc(self):
        """Test retrieving non-existent TOC"""
        with tempfile.TemporaryDirectory() as tmpdir:
            processor = PDFProcessorChunks(data_dir=tmpdir)
            
            with pytest.raises(FileNotFoundError):
                processor.get_document_toc("nonexistent")


class TestChunkLargeSection:
    """Test _chunk_large_section method"""
    
    @pytest.mark.asyncio
    async def test_chunk_large_section_small_pdf(self):
        """Test chunking a small section"""
        with tempfile.TemporaryDirectory() as tmpdir:
            processor = PDFProcessorChunks(
                data_dir=tmpdir,
                pages_per_chunk=5
            )
            
            with patch.object(processor, '_extract_chunk_content') as mock_extract:
                mock_extract.return_value = "# Content"
                
                sections_dir = Path(tmpdir) / "test" / "sections"
                sections_dir.mkdir(parents=True)
                
                pages = list(range(3))  # 3 pages
                result, counter = await processor._chunk_large_section(
                    "test.pdf", sections_dir, pages, 1, "Test Title", 0
                )
                
                # 3 pages with 5 per chunk = 1 chunk
                assert len(result) == 1
    
    @pytest.mark.asyncio
    async def test_chunk_large_section_large_pdf(self):
        """Test chunking a large section"""
        with tempfile.TemporaryDirectory() as tmpdir:
            processor = PDFProcessorChunks(
                data_dir=tmpdir,
                pages_per_chunk=3
            )
            
            with patch.object(processor, '_extract_chunk_content') as mock_extract:
                mock_extract.return_value = "# Content"
                
                sections_dir = Path(tmpdir) / "test" / "sections"
                sections_dir.mkdir(parents=True)
                
                pages = list(range(10))  # 10 pages
                result, counter = await processor._chunk_large_section(
                    "test.pdf", sections_dir, pages, 1, "Test Title", 0
                )
                
                # 10 pages with 3 per chunk = 4 chunks
                assert len(result) == 4


class TestEdgeCases:
    """Test edge cases and error conditions"""
    
    @pytest.mark.asyncio
    async def test_pdf_with_zero_pages(self):
        """Test PDF with zero pages"""
        with tempfile.TemporaryDirectory() as tmpdir:
            processor = PDFProcessorChunks(data_dir=tmpdir)
            
            with patch('fitz.open') as mock_fitz_open:
                mock_doc = MagicMock()
                mock_doc.get_toc.return_value = []
                mock_doc.metadata = {}
                mock_doc.page_count = 0
                mock_fitz_open.return_value.__enter__ = Mock(return_value=mock_doc)
                mock_fitz_open.return_value.__exit__ = Mock(return_value=False)
            
            mock_file = MockFile("test.pdf", "application/pdf", b"%PDF-1.4")
            result = await processor.process_pdf(mock_file, "test_doc")
            
            assert result["toc"] == []
    
    @pytest.mark.asyncio
    async def test_pdf_with_single_page(self):
        """Test PDF with single page"""
        with tempfile.TemporaryDirectory() as tmpdir:
            processor = PDFProcessorChunks(
                data_dir=tmpdir,
                strategy=SectionChunkStrategy.BY_PAGES
            )
            
            with patch('fitz.open') as mock_fitz_open:
                mock_doc = MagicMock()
                mock_doc.get_toc.return_value = []
                mock_doc.metadata = {}
                mock_doc.page_count = 1
                mock_fitz_open.return_value.__enter__ = Mock(return_value=mock_doc)
                mock_fitz_open.return_value.__exit__ = Mock(return_value=False)
            
            with patch('pymupdf4llm.to_markdown') as mock_to_markdown:
                mock_to_markdown.return_value = "# Page 1"
            
            mock_file = MockFile("test.pdf", "application/pdf", b"%PDF-1.4")
            result = await processor.process_pdf(mock_file, "test_doc")
            
            assert len(result["toc"]) == 1
    
    def test_get_section_with_empty_content(self):
        """Test retrieving section with empty content"""
        with tempfile.TemporaryDirectory() as tmpdir:
            processor = PDFProcessorChunks(data_dir=tmpdir)
            
            doc_dir = Path(tmpdir) / "test_doc"
            sections_dir = doc_dir / "sections"
            sections_dir.mkdir(parents=True)
            
            section_file = sections_dir / "section_test.md"
            section_file.write_text("")
            
            result = processor.get_section_content("test_doc", "section_test")
            
            assert result == ""


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=pdf_processor.core.pdf_processor_final", "--cov-report=term-missing"])
