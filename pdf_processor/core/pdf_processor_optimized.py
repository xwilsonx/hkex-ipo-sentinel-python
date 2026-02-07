"""
Optimized PDF Processor with improved performance and design patterns
Uses batched processing and proper resource management to avoid timeouts
"""
import asyncio
import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
import aiofiles
import pymupdf4llm
import fitz
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class ProcessingStrategy(Enum):
    """Different strategies for PDF processing"""
    SEQUENTIAL = "sequential"  # Process pages one by one (reliable)
    BATCHED = "batched"  # Process in small batches (balanced)
    FAST = "fast"  # Extract TOC only, no content (quickest)


@dataclass
class ProcessingConfig:
    """Configuration for PDF processing"""
    strategy: ProcessingStrategy = ProcessingStrategy.BATCHED
    batch_size: int = 10  # Number of pages to process at once
    max_workers: int = 2  # Number of concurrent workers
    extract_content: bool = True  # Whether to extract content or just TOC


class PageExtractor(ABC):
    """Abstract base class for page extraction strategies"""
    
    @abstractmethod
    async def extract_pages(self, pdf_path: str, page_numbers: List[int]) -> str:
        """Extract content from specified pages"""
        pass


class SequentialPageExtractor(PageExtractor):
    """Extract pages sequentially - most reliable"""
    
    async def extract_pages(self, pdf_path: str, page_numbers: List[int]) -> str:
        content_parts = []
        
        for page_num in sorted(page_numbers):
            try:
                # Extract single page content
                loop = asyncio.get_event_loop()
                md_text = await loop.run_in_executor(
                    None,
                    lambda: pymupdf4llm.to_markdown(pdf_path, pages=[page_num])
                )
                if md_text and md_text.strip():
                    content_parts.append(md_text.strip())
            except Exception as e:
                logger.warning(f"Error extracting page {page_num}: {e}")
                continue
        
        return "\n\n".join(content_parts)


class BatchedPageExtractor(PageExtractor):
    """Extract pages in batches for better performance"""
    
    def __init__(self, batch_size: int = 10):
        self.batch_size = batch_size
    
    async def extract_pages(self, pdf_path: str, page_numbers: List[int]) -> str:
        import concurrent.futures
        
        def extract_batch(batch: List[int]) -> str:
            content = []
            for page_num in sorted(batch):
                try:
                    md_text = pymupdf4llm.to_markdown(pdf_path, pages=[page_num])
                    if md_text and md_text.strip():
                        content.append(md_text.strip())
                except Exception:
                    continue
            return "\n\n".join(content)
        
        # Split into batches
        batches = [
            page_numbers[i:i + self.batch_size]
            for i in range(0, len(page_numbers), self.batch_size)
        ]
        
        content_parts = []
        loop = asyncio.get_event_loop()
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                loop.run_in_executor(executor, extract_batch, batch)
                for batch in batches
            ]
            results = await asyncio.gather(*futures, return_exceptions=True)
            
            for result in results:
                if not isinstance(result, Exception) and result:
                    content_parts.append(result)
        
        return "\n\n".join(content_parts)


class PDFProcessorOptimized:
    """
    Optimized PDF processor with better performance and reliability
    Uses batched page extraction to avoid timeouts
    """
    
    def __init__(self, data_dir: str = "data", config: Optional[ProcessingConfig] = None):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.config = config or ProcessingConfig()
        
        # Select appropriate extractor based on strategy
        if self.config.strategy == ProcessingStrategy.SEQUENTIAL:
            self.extractor = SequentialPageExtractor()
        else:
            self.extractor = BatchedPageExtractor(batch_size=self.config.batch_size)
    
    async def process_pdf(self, file, doc_id: str) -> Dict[str, Any]:
        """
        Process uploaded PDF file and extract TOC with section content paths
        """
        doc_dir = self.data_dir / doc_id
        doc_dir.mkdir(exist_ok=True)
        
        temp_file_path = doc_dir / f"{doc_id}_temp.pdf"
        
        try:
            # Save uploaded file
            async with aiofiles.open(temp_file_path, 'wb') as temp_file:
                content = await file.read()
                await temp_file.write(content)
            
            # Extract TOC and content
            toc_data, metadata_info = await self._extract_toc_and_sections(
                str(temp_file_path), doc_id
            )
            
            # Save metadata
            metadata_path = doc_dir / "metadata.json"
            metadata = {
                **metadata_info,
                "filename": file.filename,
                "content_type": file.content_type,
                "sections_dir": str(doc_dir / "sections")
            }
            async with aiofiles.open(metadata_path, 'w') as f:
                await f.write(json.dumps(metadata, indent=2))
            
            return {
                "toc": toc_data,
                "metadata": metadata
            }
        finally:
            if temp_file_path.exists():
                temp_file_path.unlink()
    
    async def _extract_toc_and_sections(self, pdf_path: str, doc_id: str):
        """
        Extract TOC and save section content using batched processing
        """
        doc_dir = self.data_dir / doc_id
        sections_dir = doc_dir / "sections"
        sections_dir.mkdir(parents=True, exist_ok=True)
        
        # Step 1: Extract TOC (fast operation)
        doc = fitz.open(pdf_path)
        toc = doc.get_toc()
        metadata = doc.metadata
        page_count = doc.page_count
        
        logger.info(f"Processing PDF: {page_count} pages, {len(toc)} TOC entries")
        
        toc_entries = []
        
        if self.config.extract_content:
            # Step 2: Extract all pages content in batches
            if toc:
                # Extract content for each section
                for i, toc_item in enumerate(toc):
                    logger.info(f"Processing section {i+1}/{len(toc)}")
                    
                    level, title, page = toc_item
                    
                    # Create section path
                    clean_title = "".join(c for c in title if c.isalnum() or c in " _-").strip()
                    section_path = f"section_{i:03d}_{clean_title}"
                    
                    # Determine page range
                    if i < len(toc) - 1:
                        next_page = toc[i + 1][2]
                        pages = list(range(page - 1, min(next_page - 1, page_count)))
                    else:
                        pages = list(range(page - 1, page_count))
                    
                    if pages:
                        # Extract content for this section
                        if len(pages) > 50:
                            # Large section - process in sub-batches
                            content = await self._extract_large_section(pdf_path, pages)
                        else:
                            # Small section - extract directly
                            content = await self.extractor.extract_pages(pdf_path, pages)
                        
                        # Save content
                        section_file = sections_dir / f"{section_path}.md"
                        async with aiofiles.open(section_file, 'w') as f:
                            await f.write(content)
                    
                    toc_entries.append({
                        "level": level,
                        "title": title,
                        "page": page,
                        "section_path": section_path
                    })
            else:
                # No TOC - extract all content as single section
                all_pages = list(range(page_count))
                if all_pages:
                    content = await self._extract_large_section(pdf_path, all_pages)
                    
                    section_path = "section_000_full_document"
                    section_file = sections_dir / f"{section_path}.md"
                    async with aiofiles.open(section_file, 'w') as f:
                        await f.write(content)
        else:
            # Just extract TOC, no content
            for i, toc_item in enumerate(toc):
                level, title, page = toc_item
                clean_title = "".join(c for c in title if c.isalnum() or c in " _-").strip()
                section_path = f"section_{i:03d}_{clean_title}"
                
                toc_entries.append({
                    "level": level,
                    "title": title,
                    "page": page,
                    "section_path": section_path
                })
        
        # Save TOC
        toc_file = doc_dir / "toc.json"
        async with aiofiles.open(toc_file, 'w') as f:
            await f.write(json.dumps({
                "entries": toc_entries,
                "metadata": metadata,
                "page_count": page_count
            }, indent=2))
        
        doc.close()
        
        return toc_entries, metadata
    
    async def _extract_large_section(self, pdf_path: str, page_numbers: List[int]) -> str:
        """Extract content for a large section by processing in sub-batches"""
        batch_size = 20  # Process 20 pages at a time for large sections
        
        content_parts = []
        total_pages = len(page_numbers)
        
        for i in range(0, total_pages, batch_size):
            batch = page_numbers[i:i + batch_size]
            logger.info(f"  Processing pages {i+1}-{min(i+batch_size, total_pages)}/{total_pages}")
            
            content = await self.extractor.extract_pages(pdf_path, batch)
            if content:
                content_parts.append(content)
        
        return "\n\n".join(content_parts)
    
    def get_section_content(self, doc_id: str, section_path: str) -> str:
        """Retrieve content of a specific section"""
        doc_dir = self.data_dir / doc_id
        section_file = doc_dir / "sections" / f"{section_path}.md"
        
        if not section_file.exists():
            raise FileNotFoundError(f"Section content not found: {section_path}")
        
        return section_file.read_text()
    
    def get_document_toc(self, doc_id: str) -> Dict[str, Any]:
        """Get the TOC for a processed document"""
        doc_dir = self.data_dir / doc_id
        toc_file = doc_dir / "toc.json"
        
        if not toc_file.exists():
            raise FileNotFoundError(f"Document TOC not found: {doc_id}")
        
        return json.loads(toc_file.read_text())


# Backward compatibility alias
PDFProcessor = PDFProcessorOptimized
