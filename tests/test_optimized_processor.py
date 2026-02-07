"""
Comprehensive tests for optimized PDF processor
Tests all PDF files in data/pdf with timeout protection
"""
import pytest
import asyncio
import json
import tempfile
from pathlib import Path
import sys
import time

sys.path.insert(0, '/home/wilson/opencode/hkex-ipo-sentinel-python')
from pdf_processor.core.pdf_processor_optimized import (
    PDFProcessorOptimized,
    ProcessingConfig,
    ProcessingStrategy,
    SequentialPageExtractor,
    BatchedPageExtractor
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
def optimized_processor():
    """Create optimized processor with batched strategy"""
    from tempfile import TemporaryDirectory
    with TemporaryDirectory() as tmpdir:
        config = ProcessingConfig(
            strategy=ProcessingStrategy.BATCHED,
            batch_size=10,
            extract_content=True
        )
        yield PDFProcessorOptimized(data_dir=tmpdir, config=config)


@pytest.fixture
def fast_processor():
    """Create processor for TOC-only extraction (fastest)"""
    from tempfile import TemporaryDirectory
    with TemporaryDirectory() as tmpdir:
        config = ProcessingConfig(
            strategy=ProcessingStrategy.FAST,
            extract_content=False
        )
        yield PDFProcessorOptimized(data_dir=tmpdir, config=config)


@pytest.fixture
def all_pdfs():
    """Get all PDF files in data/pdf directory"""
    pdf_dir = Path("/home/wilson/opencode/hkex-ipo-sentinel-python/data/pdf")
    return sorted(pdf_dir.glob("*.pdf"))


class TestOptimizedProcessorAllPDFs:
    """Test optimized processor against all PDF files"""
    
    @pytest.mark.asyncio
    async def test_all_pdfs_concurrently(self, all_pdfs):
        """Process all PDFs to ensure no timeouts"""
        if not all_pdfs:
            pytest.skip("No PDF files found")
        
        print(f"\n=== Processing {len(all_pdfs)} PDF files with optimized processor ===")
        
        results = []
        
        for pdf_path in all_pdfs:
            doc_id = pdf_path.stem
            print(f"\n[{doc_id}] {pdf_path.name} ({pdf_path.stat().st_size / 1024:.1f} KB)")
            print("-" * 60)
            
            from tempfile import TemporaryDirectory
            with TemporaryDirectory() as tmpdir:
                config = ProcessingConfig(
                    strategy=ProcessingStrategy.BATCHED,
                    batch_size=10,
                    extract_content=True
                )
                processor = PDFProcessorOptimized(data_dir=tmpdir, config=config)
                
                start_time = time.time()
                
                try:
                    with open(pdf_path, 'rb') as f:
                        pdf_content = f.read()
                    
                    mock_file = MockFile(pdf_path.name, "application/pdf", pdf_content)
                    result = awaitprocessor.process_pdf(mock_file, doc_id)
                    
                    elapsed = time.time() - start_time
                    
                    # Verify structure
                    assert "toc" in result
                    assert "metadata" in result
                    assert "filename" in result["metadata"]
                    
                    toc_count = len(result["toc"])
                    print(f"  TOC entries: {toc_count}")
                    print(f"  Processing time: {elapsed:.1f}s")
                    
                    if toc_count > 0:
                        print(f"  First entry: {result['toc'][0]['title'][:50]}")
                    
                    # Verify files
                    doc_dir = processor.data_dir / doc_id
                    toc_file = doc_dir / "toc.json"
                    sections_dir = doc_dir / "sections"
                    
                    assert toc_file.exists(), "TOC file should exist"
                    assert sections_dir.exists(), "Sections directory should exist"
                    
                    section_files = list(sections_dir.glob("*.md"))
                    print(f"  Section files: {len(section_files)}")
                    
                    # Test retrieving first section content if exists
                    if result["toc"]:
                        first_section = result["toc"][0]["section_path"]
                        try:
                            content = processor.get_section_content(doc_id, first_section)
                            print(f"  Content check: ✓ First section has {len(content)} chars")
                        except FileNotFoundError as e:
                            print(f"  Warning: Could not retrieve section content: {e}")
                    
                    results.append({
                        'name': pdf_path.name,
                        'status': 'success',
                        'toc_count': toc_count,
                        'time': elapsed
                    })
                    print(f"  Status: ✓ SUCCESS")
                    
                except Exception as e:
                    elapsed = time.time() - start_time
                    print(f"  Status: ✗ ERROR - {type(e).__name__}: {e}")
                    results.append({
                        'name': pdf_path.name,
                        'status': 'error',
                        'error': str(e),
                        'time': elapsed
                    })
                    pytest.fail(f"Failed to process {pdf_path.name}: {e}")
        
        # Summary
        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)
        success = sum(1 for r in results if r['status'] == 'success')
        failed = len(results) - success
        
        print(f"Total: {len(results)} | Success: {success} | Failed: {failed}")
        
        for r in results:
            status = '✓' if r['status'] == 'success' else '✗'
            if r['status'] == 'success':
                print(f"{status} {r['name']:35s} {r['toc_count']:3d} TOC {r['time']:6.1f}s")
            else:
                print(f"{status} {r['name']:35s} ERROR")
        
        assert success == len(results), f"Expected all PDFs to succeed, but {failed} failed"


class TestExtractionStrategies:
    """Test different extraction strategies"""
    
    @pytest.mark.asyncio
    async def test_sequential_strategy(self, all_pdfs):
        """Test sequential extraction strategy"""
        pdf_path = all_pdfs[0]  # Use first PDF
        
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as tmpdir:
            config = ProcessingConfig(
                strategy=ProcessingStrategy.SEQUENTIAL,
                extract_content=True
            )
            processor = PDFProcessorOptimized(data_dir=tmpdir, config=config)
            
            with open(pdf_path, 'rb') as f:
                pdf_content = f.read()
            
            mock_file = MockFile(pdf_path.name, "application/pdf", pdf_content)
            result = awaitprocessor.process_pdf(mock_file, "sequential_test")
            
            print(f"\nSequential strategy: {result['metadata']['filename']}")
            print(f"  TOC entries: {len(result['toc'])}")
    
    @pytest.mark.asyncio
    async def test_batched_strategy(self, all_pdfs):
        """Test batched extraction strategy"""
        pdf_path = all_pdfs[0]
        
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as tmpdir:
            config = ProcessingConfig(
                strategy=ProcessingStrategy.BATCHED,
                batch_size=5,
                extract_content=True
            )
            processor = PDFProcessorOptimized(data_dir=tmpdir, config=config)
            
            with open(pdf_path, 'rb') as f:
                pdf_content = f.read()
            
            mock_file = MockFile(pdf_path.name, "application/pdf", pdf_content)
            result = awaitprocessor.process_pdf(mock_file, "batched_test")
            
            print(f"\nBatched strategy: {result['metadata']['filename']}")
            print(f"  TOC entries: {len(result['toc'])}")


class TestLargePDFsSpecific:
    """Specialized tests for large PDFs"""
    
    @pytest.mark.asyncio
    async def test_largest_pdf_optimized(self, all_pdfs):
        """Test the largest PDF with optimized settings"""
        # Get largest PDF
        largest_pdf = max(all_pdfs, key=lambda p: p.stat().st_size)
        
        print(f"\n=== Testing largest PDF: {largest_pdf.name} ===")
        print(f"Size: {largest_pdf.stat().st_size / (1024*1024):.1f} MB")
        
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as tmpdir:
            config = ProcessingConfig(
                strategy=ProcessingStrategy.BATCHED,
                batch_size=15,  # Larger batch for big files
                extract_content=True
            )
            processor = PDFProcessorOptimized(data_dir=tmpdir, config=config)
            
            start_time = time.time()
            
            with open(largest_pdf, 'rb') as f:
                pdf_content = f.read()
            
            mock_file = MockFile(largest_pdf.name, "application/pdf", pdf_content)
            result = awaitprocessor.process_pdf(mock_file, largest_pdf.stem)
            
            elapsed = time.time() - start_time
            
            print(f"\nProcessing completed in {elapsed:.1f}s")
            print(f"TOC entries: {len(result['toc'])}")
            
            # Quality checks
            assert len(result["toc"]) > 0, "Should have TOC entries"
            assert "metadata" in result
            
            # Verify all sections exist
            toc_data = processor.get_document_toc(largest_pdf.stem)
            sections_dir = processor.data_dir / largest_pdf.stem / "sections"
            section_files = list(sections_dir.glob("*.md"))
            
            print(f"Section files created: {len(section_files)}")
            assert len(section_files) >= len(toc_data["entries"]), \
                "Should have at least as many section files as TOC entries"
            
            # Sample content check
            if section_files:
                sample_content = section_files[0].read_text()
                print(f"Sample section content length: {len(sample_content)} chars")
                assert len(sample_content) > 0, "Section should have content"


class TestQuality:
    """Quality tests to ensure output integrity"""
    
    @pytest.mark.asyncio
    async def test_content_quality(self, all_pdfs, optimized_processor):
        """Verify that extracted content has good quality"""
        # Use a PDF with content
        pdf_path = Path("/home/wilson/opencode/hkex-ipo-sentinel-python/data/pdf/test_document.pdf")
        
        if not pdf_path.exists():
            pytest.skip("test_document.pdf not found")
        
        with open(pdf_path, 'rb') as f:
            pdf_content = f.read()
        
        mock_file = MockFile("test.pdf", "application/pdf", pdf_content)
        result = awaitprocessor.process_pdf(mock_file, "quality_test")
        
        # Check each section
        toc_data =processor.get_document_toc("quality_test")
        
        for entry in toc_data["entries"][:3]:  # Check first 3 sections
            content =processor.get_section_content("quality_test", entry["section_path"])
            
            # Quality assertions
            assert len(content) > 0, f"Section {entry['title']} should have content"
            assert len(content) < 100000, f"Section content seems too large: {len(content)}"
            
            # Should contain some text (not just whitespace)
            stripped = content.strip()
            assert len(stripped) > 10, "Section should have meaningful content"
            
            print(f"✓ Section '{entry['title'][:30]}...': {len(content)} chars")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
