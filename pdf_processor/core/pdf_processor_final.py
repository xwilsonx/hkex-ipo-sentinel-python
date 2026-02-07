"""
Final optimized PDF processor with small section chunks
Creates smaller, manageable sections to avoid timeouts and improve performance
"""
import asyncio
import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
import aiofiles
import pymupdf4llm
import fitz

logger = logging.getLogger(__name__)


class SectionChunkStrategy:
    """Strategy for creating section chunks"""
    
    BY_TOC = "by_toc"  # One section per TOC entry (may be large)
    BY_PAGES = "by_pages"  # Split into fixed page chunks
    BY_TOC_CHUNKED = "by_toc_chunked"  # TOC-based but chunk large sections


class PDFProcessorChunks:
    """
    PDF processor that creates small section chunks for better performance
    """
    
    def __init__(
        self,
        data_dir: str = "data",
        strategy: str = SectionChunkStrategy.BY_PAGES,
        pages_per_chunk: int = 15,
        max_section_size: int = 50  # Max pages for TOC-based sections
    ):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.strategy = strategy
        self.pages_per_chunk = pages_per_chunk
        self.max_section_size = max_section_size
    
    async def process_pdf(self, file, doc_id: str) -> Dict[str, Any]:
        """Process uploaded PDF file"""
        doc_dir = self.data_dir / doc_id
        doc_dir.mkdir(exist_ok=True)
        
        temp_file_path = doc_dir / f"{doc_id}_temp.pdf"
        
        try:
            # Save uploaded file
            async with aiofiles.open(temp_file_path, 'wb') as temp_file:
                content = await file.read()
                await temp_file.write(content)
            
            # Extract structure and content
            toc_data, metadata, page_count = await self._extract_with_chunks(
                str(temp_file_path), doc_id
            )
            
            # Save metadata
            metadata_path = doc_dir / "metadata.json"
            metadata_info = {
                "filename": file.filename,
                "content_type": file.content_type,
                "sections_dir": str(doc_dir / "sections"),
                "strategy": self.strategy,
                "total_pages": page_count,
                **metadata
            }
            async with aiofiles.open(metadata_path, 'w') as f:
                await f.write(json.dumps(metadata_info, indent=2))
            
            return {
                "toc": toc_data,
                "metadata": metadata_info
            }
        finally:
            if temp_file_path.exists():
                temp_file_path.unlink()
    
    async def _extract_with_chunks(self, pdf_path: str, doc_id: str):
        """Extract PDF with chunked sections"""
        doc_dir = self.data_dir / doc_id
        sections_dir = doc_dir / "sections"
        sections_dir.mkdir(parents=True, exist_ok=True)
        
        # Open PDF and get structure
        doc = fitz.open(pdf_path)
        toc = doc.get_toc()
        metadata = doc.metadata
        page_count = doc.page_count
        
        logger.info(f"Processing {doc_id}: {page_count} pages, {len(toc)} TOC entries")
        
        toc_entries = []
        section_counter = 0
        
        if self.strategy == SectionChunkStrategy.BY_PAGES:
            # Create fixed-size page chunks
            toc_entries, section_counter = await self._create_page_chunks(
                pdf_path, doc_id, sections_dir, page_count, section_counter, toc
            )
        elif self.strategy == SectionChunkStrategy.BY_TOC_CHUNKED:
            # TOC-based but chunk large sections
            toc_entries, section_counter = await self._create_toc_chunked(
                pdf_path, doc_id, sections_dir, toc, page_count, section_counter
            )
        else:
            # Original TOC strategy (may have large sections)
            toc_entries, section_counter = await self._create_toc_based(
                pdf_path, doc_id, sections_dir, toc, page_count, section_counter
            )
        
        # Save TOC
        toc_file = doc_dir / "toc.json"
        async with aiofiles.open(toc_file, 'w') as f:
            await f.write(json.dumps({
                "entries": toc_entries,
                "metadata": metadata,
                "page_count": page_count
            }, indent=2))
        
        doc.close()
        
        return toc_entries, metadata, page_count
    
    async def _create_page_chunks(
        self, pdf_path: str, doc_id: str, sections_dir: Path,
        page_count: int, section_counter: int, toc: List
    ) -> tuple:
        """Create sections based on fixed page chunks"""
        toc_entries = []
        
        # Create chunks
        for start_page in range(0, page_count, self.pages_per_chunk):
            end_page = min(start_page + self.pages_per_chunk, page_count)
            pages = list(range(start_page, end_page))
            
            section_path = f"section_{section_counter:03d}_pages_{start_page+1}-{end_page}"
            
            # Extract content
            content = await self._extract_chunk_content(pdf_path, pages)
            
            # Save section
            section_file = sections_dir / f"{section_path}.md"
            async with aiofiles.open(section_file, 'w') as f:
                await f.write(content)
            
            # Map TOC entries to this section
            related_toc = self._find_toc_entries_for_pages(toc, pages)
            
            toc_entries.append({
                "level": 1,
                "title": f"Pages {start_page + 1}-{end_page}" + 
                         (f": {related_toc[0][1]}" if related_toc else ""),
                "page": start_page + 1,
                "section_path": section_path,
                "page_range": [start_page + 1, end_page],
                "related_toc": [item[1] for item in related_toc]
            })
            
            section_counter += 1
            logger.info(f"Created chunk {section_counter}: pages {start_page+1}-{end_page}")
        
        return toc_entries, section_counter
    
    async def _create_toc_chunked(
        self, pdf_path: str, doc_id: str, sections_dir: Path,
        toc: List, page_count: int, section_counter: int
    ) -> tuple:
        """Create sections based on TOC but chunk large ones"""
        toc_entries = []
        
        for i, toc_item in enumerate(toc):
            level, title, page = toc_item
            
            # Determine page range for this TOC entry
            if i < len(toc) - 1:
                next_page = toc[i + 1][2]
                pages = list(range(page - 1, min(next_page - 1, page_count)))
            else:
                pages = list(range(page - 1, page_count))
            
            if len(pages) > self.max_section_size:
                # Chunk this large section
                chunk_toc_entries, section_counter = await self._chunk_large_section(
                    pdf_path, sections_dir, pages, level, title, section_counter
                )
                toc_entries.extend(chunk_toc_entries)
            else:
                # Normal section
                section_path = f"section_{section_counter:03d}_{self._clean_title(title)}"
                content = await self._extract_chunk_content(pdf_path, pages)
                
                section_file = sections_dir / f"{section_path}.md"
                async with aiofiles.open(section_file, 'w') as f:
                    await f.write(content)
                
                toc_entries.append({
                    "level": level,
                    "title": title,
                    "page": page,
                    "section_path": section_path
                })
                section_counter += 1
            
            logger.info(f"Processed TOC entry {i+1}/{len(toc)}: {title} -> {section_counter-1} sections")
        
        return toc_entries, section_counter
    
    async def _create_toc_based(
        self, pdf_path: str, doc_id: str, sections_dir: Path,
        toc: List, page_count: int, section_counter: int
    ) -> tuple:
        """Original TOC-based strategy (for comparison)"""
        toc_entries = []
        
        for i, toc_item in enumerate(toc):
            level, title, page = toc_item
            
            if i < len(toc) - 1:
                next_page = toc[i + 1][2]
                pages = list(range(page - 1, min(next_page - 1, page_count)))
            else:
                pages = list(range(page - 1, page_count))
            
            if pages:
                section_path = f"section_{section_counter:03d}_{self._clean_title(title)}"
                content = await self._extract_chunk_content(pdf_path, pages)
                
                section_file = sections_dir / f"{section_path}.md"
                async with aiofiles.open(section_file, 'w') as f:
                    await f.write(content)
                
                toc_entries.append({
                    "level": level,
                    "title": title,
                    "page": page,
                    "section_path": section_path
                })
                section_counter += 1
        
        return toc_entries, section_counter
    
    async def _chunk_large_section(
        self, pdf_path: str, sections_dir: Path, pages: List[int],
        level: int, title: str, section_counter: int
    ) -> tuple:
        """Split a large section into chunks"""
        toc_entries = []
        num_chunks = (len(pages) + self.pages_per_chunk - 1) // self.pages_per_chunk
        
        for chunk_idx in range(num_chunks):
            start_idx = chunk_idx * self.pages_per_chunk
            end_idx = min(start_idx + self.pages_per_chunk, len(pages))
            chunk_pages = pages[start_idx:end_idx]
            
            section_path = f"section_{section_counter:03d}_{self._clean_title(title)}_part{chunk_idx+1}"
            content = await self._extract_chunk_content(pdf_path, chunk_pages)
            
            section_file = sections_dir / f"{section_path}.md"
            async with aiofiles.open(section_file, 'w') as f:
                await f.write(content)
            
            toc_entries.append({
                "level": level,
                "title": f"{title} (Part {chunk_idx + 1}/{num_chunks})",
                "page": chunk_pages[0] + 1,
                "section_path": section_path,
                "parent_title": title
            })
            section_counter += 1
        
        return toc_entries, section_counter
    
    async def _extract_chunk_content(self, pdf_path: str, pages: List[int]) -> str:
        """Extract content for a chunk of pages"""
        content_parts = []
        
        for page_num in sorted(pages):
            try:
                loop = asyncio.get_event_loop()
                md_text = await loop.run_in_executor(
                    None,
                    lambda: pymupdf4llm.to_markdown(pdf_path, pages=[page_num])
                )
                if md_text and md_text.strip():
                    content_parts.append(md_text.strip())
            except Exception as e:
                logger.warning(f"Error extracting page {page_num}: {e}")
        
        return "\n\n".join(content_parts)
    
    def _find_toc_entries_for_pages(self, toc: List, pages: List[int]) -> List:
        """Find TOC entries that occur within a page range"""
        related = []
        for entry in toc:
            level, title, page_num = entry
            page_idx = page_num - 1  # Convert to 0-indexed
            if page_idx in pages or (pages and page_idx == pages[0]):
                related.append(entry)
        return related
    
    def _clean_title(self, title: str) -> str:
        """Clean title for use in file names"""
        return "".join(c for c in title if c.isalnum() or c in " _-").strip()[:50]
    
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


# Backward compatibility
PDFProcessor = PDFProcessorChunks
