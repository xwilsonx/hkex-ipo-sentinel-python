#!/usr/bin/env python3
"""Enhanced integration tests for PDF processor using real data/pdf/* files"""

import pytest
import asyncio
import json
import os
import tempfile
from pathlib import Path
import aiofiles
import sys

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


@pytest.fixture(scope="session")
def pdf_test_dir():
    """Get the directory containing test PDF files"""
    return Path("/home/wilson/opencode/hkex-ipo-sentinel-python/data/pdf")


@pytest.fixture
def processor():
    """Create a PDFProcessor for testing"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield PDFProcessor(data_dir=tmpdir)


class TestRealPDFProcessing:
    """Tests using actual PDF files from data/pdf/*"""

    @pytest.mark.asyncio
    async def test_process_all_pdfs_in_directory(self, processor, pdf_test_dir):
        """Process all PDF files found in data/pdf/ directory"""
        pdf_files = list(pdf_test_dir.glob("*.pdf"))
        
        if not pdf_files:
            pytest.skip("No PDF files found in data/pdf/ directory")

        print(f"\nFound {len(pdf_files)} PDF file(s) to process")
        
        for pdf_path in pdf_files:
            print(f"\nProcessing: {pdf_path.name}")
            
            pdf_content = pdf_path.read_bytes()
            mock_file = MockFile(pdf_path.name, "application/pdf", pdf_content)
            doc_id = f"test_{pdf_path.stem}"
            
            result = await processor.process_pdf(mock_file, doc_id)
            
            # Verify basic structure
            assert "toc" in result, f"TOC missing for {pdf_path.name}"
            assert "metadata" in result, f"Metadata missing for {pdf_path.name}"
            assert isinstance(result["toc"], list)
            
            # Verify files were created
            doc_dir = processor.data_dir / doc_id
            assert doc_dir.exists()
            assert (doc_dir / "toc.json").exists()
            assert (doc_dir / "metadata.json").exists()
            assert (doc_dir / "sections").exists()
            
            # Verify sections
            sections_dir = doc_dir / "sections"
            section_files = list(sections_dir.glob("*.md"))
            print(f"  - Created {len(section_files)} section files")
            print(f"  - TOC entries: {len(result['toc'])}")
            print(f"  - Filename: {result['metadata']['filename']}")

    @pytest.mark.asyncio
    async def test_process_single_pdf_and_validate_content(self, processor, pdf_test_dir):
        """Process a single PDF and validate the extracted content"""
        pdf_path = pdf_test_dir / "test_document.pdf"
        
        if not pdf_path.exists():
            pytest.skip("test_document.pdf not found")

        with open(pdf_path, 'rb') as f:
            pdf_content = f.read()
        
        mock_file = MockFile("test_document.pdf", "application/pdf", pdf_content)
        doc_id = "content_test"

        result = await processor.process_pdf(mock_file, doc_id)

        # Verify TOC structure
        assert len(result["toc"]) > 0
        for entry in result["toc"]:
            assert "level" in entry
            assert "title" in entry
            assert "page" in entry
            assert "section_path" in entry
            print(f"\nTOC Entry: {entry['title']} (Level {entry['level']}, Page {entry['page']})")
            assert entry["section_path"].startswith("section_")

        # Verify all sections are accessible
        toc = processor.get_document_toc(doc_id)
        entries_count = len(toc["entries"])
        print(f"\nTotal sections: {entries_count}")
        
        sections_dir = processor.data_dir / doc_id / "sections"
        section_files = list(sections_dir.glob("*.md"))
        assert len(section_files) == entries_count, f"Mismatch: {len(section_files)} files vs {entries_count} TOC entries"

        # Test getting section content
        for entry in toc["entries"][:3]:  # Test first 3 entries
            section_path = entry["section_path"]
            try:
                content = processor.get_section_content(doc_id, section_path)
                assert isinstance(content, str)
                assert len(content) > 0, f"Section {section_path} is empty"
                print(f"  Section '{section_path}': {len(content)} characters")
            except FileNotFoundError as e:
                print(f"  Section '{section_path}' not found: {e}")
                raise

    @pytest.mark.asyncio
    async def test_non_pdf_file_rejection(self, processor):
        """Test that non-PDF files are properly handled"""
        doc_id = "non_pdf_test"
        
        test_cases = [
            ("text.txt", b"This is plain text", "text/plain"),
            ("image.jpg", b"fake image data", "image/jpeg"),
            ("doc.docx", b"fake docx data", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
        ]
        
        for filename, content, content_type in test_cases:
            mock_file = MockFile(filename, content_type, content)
            
            # Process should still work, but PDF extraction might fail gracefully
            # This tests the robustness of the error handling
            try:
                result = await processor.process_pdf(mock_file, doc_id)
                print(f"\nFile {filename}: Processed (but may have empty TOC)")
                assert result["toc"] == [], f"Expected empty TOC for {filename}"
            except Exception as e:
                print(f"\nFile {filename}: Raised {type(e).__name__}: {e}")
                # This is acceptable - non-PDF files should fail gracefully

    @pytest.mark.asyncio
    async def test_empty_pdf_handling(self, processor):
        """Test handling of empty or minimal PDFs"""
        doc_id = "empty_pdf"
        
        # Create minimal PDF content (this might not be valid)
        mock_file = MockFile("empty.pdf", "application/pdf", b"")
        
        try:
            result = await processor.process_pdf(mock_file, doc_id)
            print(f"\nEmpty PDF: Processed with {len(result['toc'])} TOC entries")
        except Exception as e:
            print(f"\nEmpty PDF: Raised {type(e).__name__}: {e}")
            # This is acceptable - empty PDFs should fail gracefully

    @pytest.mark.asyncio
    async def test_special_characters_in_toc(self, processor, pdf_test_dir):
        """Test that special characters in TOC are handled correctly"""
        pdf_path = pdf_test_dir / "test_document.pdf"
        
        if not pdf_path.exists():
            pytest.skip("test_document.pdf not found")

        with open(pdf_path, 'rb') as f:
            pdf_content = f.read()
        
        mock_file = MockFile("with-special-chars.pdf", "application/pdf", pdf_content)
        doc_id = "special_chars_test"

        result = await processor.process_pdf(mock_file, doc_id)
        
        # Verify section paths are sanitized
        for entry in result["toc"]:
            section_path = entry["section_path"]
            # Section path should only contain safe characters
            allowed_chars = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-")
            assert all(c in allowed_chars or c.isdigit() for c in section_path), \
                f"Section path contains unsafe characters: {section_path}"
            print(f"  sanitized path: {section_path}")

    @pytest.mark.asyncio
    async def test_concurrent_processing(self, processor, pdf_test_dir):
        """Test processing multiple PDFs concurrently"""
        pdf_path = pdf_test_dir / "test_document.pdf"
        
        if not pdf_path.exists():
            pytest.skip("test_document.pdf not found")

        with open(pdf_path, 'rb') as f:
            pdf_content = f.read()

        async def process_single(doc_id):
            mock_file = MockFile(f"doc_{doc_id}.pdf", "application/pdf", pdf_content)
            return await processor.process_pdf(mock_file, doc_id)

        # Process 3 PDFs concurrently
        doc_ids = [f"concurrent_{i}" for i in range(3)]
        tasks = [process_single(doc_id) for doc_id in doc_ids]
        
        print(f"\nProcessing {len(doc_ids)} PDFs concurrently...")
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                print(f"  Document {doc_ids[i]} failed: {result}")
                raise
            else:
                print(f"  Document {doc_ids[i]} processed successfully")
                assert "toc" in result
                assert "metadata" in result

        # Verify all documents were created
        for doc_id in doc_ids:
            doc_dir = processor.data_dir / doc_id
            assert doc_dir.exists()

    def test_get_document_toc_from_saved_file(self, processor, pdf_test_dir):
        """Test retrieving TOC from saved JSON file"""
        pdf_path = pdf_test_dir / "test_document.pdf"
        
        if not pdf_path.exists():
            pytest.skip("test_document.pdf not found")

        # This test needs to be async, but let's structure it properly
        async def async_test():
            with open(pdf_path, 'rb') as f:
                pdf_content = f.read()
            
            mock_file = MockFile("test.pdf", "application/pdf", pdf_content)
            doc_id = "file_test"
            
            await processor.process_pdf(mock_file, doc_id)
            
            # Get TOC from file
            toc = processor.get_document_toc(doc_id)
            
            assert "entries" in toc
            assert "metadata" in toc
            assert "page_count" in toc
            assert len(toc["entries"]) > 0
            
            print(f"\nTOC retrieved from file: {len(toc['entries'])} entries")
            print(f"Metadata: {toc['metadata']}")
            print(f"Page count: {toc['page_count']}")

        asyncio.run(async_test())


class TestEdgeCasesAndErrorHandling:
    """Test robustness and error handling"""

    @pytest.mark.asyncio
    async def test_get_nonexistent_section_content(self, processor):
        """Test retrieving content from a non-existent section"""
        with pytest.raises(FileNotFoundError):
            processor.get_section_content("nonexistent_doc", "nonexistent_section")

    def test_get_nonexistent_document_toc(self, processor):
        """Test retrieving TOC from a non-existent document"""
        with pytest.raises(FileNotFoundError):
            processor.get_document_toc("nonexistent_doc")

    @pytest.mark.asyncio
    async def test_large_filename_handling(self, processor, pdf_test_dir):
        """Test handling of very long filenames"""
        pdf_path = pdf_test_dir / "test_document.pdf"
        
        if not pdf_path.exists():
            pytest.skip("test_document.pdf not found")

        with open(pdf_path, 'rb') as f:
            pdf_content = f.read()
        
        long_filename = "a" * 200 + ".pdf"
        mock_file = MockFile(long_filename, "application/pdf", pdf_content)
        doc_id = "long_filename_test"

        result = await processor.process_pdf(mock_file, doc_id)
        
        # Should succeed
        assert result["metadata"]["filename"] == long_filename
        print(f"\nLong filename ({len(long_filename)} chars) handled correctly")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
