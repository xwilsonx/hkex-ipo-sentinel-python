from pydantic import BaseModel
from typing import List, Dict, Any, Optional

class TOCEntry(BaseModel):
    """Represents a single entry in the table of contents"""
    level: int
    title: str
    page: int
    section_path: str  # Path to access the section content

class TOCResponse(BaseModel):
    """Response model for TOC extraction"""
    document_id: str
    toc: List[TOCEntry]
    metadata: Dict[str, Any]

class SectionContent(BaseModel):
    """Represents the content of a section"""
    content: str
    section_path: str