import asyncio
import json
import os
import logging
from pathlib import Path
from typing import Dict, List, Any
import aiofiles
import pymupdf4llm
import fitz

from pdf_processor.models.schemas import TOCEntry

logger = logging.getLogger(__name__)

class PDFProcessor:
    """Handles PDF processing, TOC extraction, and section content management"""
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        
    async def process_pdf(self, file, doc_id: str) -> Dict[str, Any]:
        """
        Process uploaded PDF file and extract TOC with section content paths
        """
        # Create document directory
        doc_dir = self.data_dir / doc_id
        doc_dir.mkdir(exist_ok=True)
        
        # Save uploaded file temporarily
        temp_file_path = doc_dir / f"{doc_id}_temp.pdf"
        async with aiofiles.open(temp_file_path, 'wb') as temp_file:
            content = await file.read()
            await temp_file.write(content)
        
        try:
            # Extract TOC and content
            toc_data = await self._extract_toc_and_sections(str(temp_file_path), doc_id)
            
            # Save metadata
            metadata_path = doc_dir / "metadata.json"
            metadata = {
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
            # Clean up temporary file
            if temp_file_path.exists():
                temp_file_path.unlink()
    
    async def _extract_toc_and_sections(self, pdf_path: str, doc_id: str) -> List[Dict[str, Any]]:
        """
        Extract TOC and save section content to separate files
        """
        doc_dir = self.data_dir / doc_id
        sections_dir = doc_dir / "sections"
        sections_dir.mkdir(parents=True, exist_ok=True)
        
        # Open PDF and extract TOC
        import fitz
        doc = fitz.open(pdf_path)
        toc = doc.get_toc()  # [(level, title, page_index), ...]
        
        # Also get document metadata
        metadata = doc.metadata
        page_count = doc.page_count
        
        toc_entries = []
        
        # Extract all pages at once for better performance
        if toc:
            # Extract entire document content once
            all_pages_content = await self._extract_all_pages_async(pdf_path, page_count)
            
            # Process each TOC entry using pre-extracted content
            for i, toc_item in enumerate(toc):
                level, title, page = toc_item
                
                # Create a clean section path
                clean_title = "".join(c for c in title if c.isalnum() or c in " _-").strip()
                section_path = f"section_{i:03d}_{clean_title}"
                
                # Determine page range for this section
                if i < len(toc) - 1:
                    next_page = toc[i + 1][2]
                    pages_to_extract = list(range(page - 1, next_page - 1))
                else:
                    pages_to_extract = list(range(page - 1, page_count))
                
                # Get content from pre-extracted pages
                content = self._get_content_from_pages(all_pages_content, pages_to_extract)
                
                # Save section content to file
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
            # No TOC - create a single section with all content
            section_path = "section_000_full_document"
            all_content = await self._extract_all_pages_async(pdf_path, page_count)
            
            section_file = sections_dir / f"{section_path}.md"
            async with aiofiles.open(section_file, 'w') as f:
                await f.write(all_content)
            
            toc_entries = []
        
        # Save TOC data
        toc_file = doc_dir / "toc.json"
        async with aiofiles.open(toc_file, 'w') as f:
            await f.write(json.dumps({
                "entries": toc_entries,
                "metadata": metadata,
                "page_count": page_count
            }, indent=2))
        
        doc.close()
        return toc_entries
    
    async def _extract_all_pages_async(self, pdf_path: str, page_count: int) -> List[str]:
        """
        Extract all pages content async by running in thread pool
        Returns list of markdown content per page (0-indexed)
        """
        import concurrent.futures
        
        def extract_single_page(page_num: int) -> str:
            """Extract a single page's content"""
            try:
                md_text = pymupdf4llm.to_markdown(pdf_path, pages=[page_num])
                return md_text if md_text else ""
            except Exception:
                return ""
        
        # Extract all pages in parallel using thread pool
        loop = asyncio.get_event_loop()
        
        page_contents = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            futures = [
                loop.run_in_executor(executor, extract_single_page, i)
                for i in range(page_count)
            ]
            page_contents = await asyncio.gather(*futures, return_exceptions=True)
        
        # Handle any exceptions
        result = []
        for content in page_contents:
            if isinstance(content, Exception):
                result.append("")
            else:
                result.append(content or "")
        
        return result
    
    def _get_content_from_pages(self, all_pages: List[str], page_numbers: List[int]) -> str:
        """
        Combine content from specific pages into a single markdown string
        """
        content_parts = []
        for page_num in page_numbers:
            if 0 <= page_num < len(all_pages):
                content = all_pages[page_num].strip()
                if content:
                    content_parts.append(content)
        
        return "\n\n".join(content_parts)
    
    async def _extract_pages_content(self, doc, pages_to_extract: list, pdf_path: str) -> str:
        """
        Extract content from specified pages (deprecated, kept for compatibility)
        """
        md_text = pymupdf4llm.to_markdown(pdf_path, pages=pages_to_extract)
        return md_text if md_text else ""
    
    def get_section_content(self, doc_id: str, section_path: str) -> str:
        """
        Retrieve content of a specific section
        """
        doc_dir = self.data_dir / doc_id
        section_file = doc_dir / "sections" / f"{section_path}.md"
        
        if not section_file.exists():
            raise FileNotFoundError(f"Section content not found: {section_path}")
        
        return section_file.read_text()
    
    def get_document_toc(self, doc_id: str) -> Dict[str, Any]:
        """
        Get the TOC for a processed document
        """
        doc_dir = self.data_dir / doc_id
        toc_file = doc_dir / "toc.json"
        
        if not toc_file.exists():
            raise FileNotFoundError(f"Document TOC not found: {doc_id}")
        
        return json.loads(toc_file.read_text())