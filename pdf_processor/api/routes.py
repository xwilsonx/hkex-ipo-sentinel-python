from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from pathlib import Path
from typing import Dict, Any
import json
import uuid
import logging
import re
import shutil

from pdf_processor.core.pdf_processor import PDFProcessor
from pdf_processor.models.schemas import TOCResponse

router = APIRouter()
logger = logging.getLogger(__name__)

# Initialize processor
processor = PDFProcessor()

def sanitize_filename(filename: str) -> str:
    """Sanitize filename to be used as directory name"""
    # Remove extension
    name = Path(filename).stem
    
    # Replace non-alphanumeric characters with underscore
    clean_name = re.sub(r'[^\w\-_]', '_', name)
    
    # Remove multiple underscores
    clean_name = re.sub(r'_+', '_', clean_name)
    
    # Remove leading/trailing underscores
    return clean_name.strip('_')

@router.post("/upload-pdf", response_model=TOCResponse)
async def upload_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...)
):
    """
    Upload a PDF file and extract its table of contents.
    Section content is saved to separate files for performance.
    """
    if not file.content_type.startswith("application/pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF")
    
    try:
        # Use sanitized filename as doc_id to prevent duplication
        doc_id = sanitize_filename(file.filename)
        
        # Clean up existing directory if it exists
        doc_dir = Path("data") / doc_id
        if doc_dir.exists():
            shutil.rmtree(doc_dir)
            logger.info(f"Cleaned up existing directory for {doc_id}")
            
        # Process the PDF
        toc_data = await processor.process_pdf(file, doc_id)
        
        return TOCResponse(
            document_id=doc_id,
            toc=[{
                "level": entry["level"],
                "title": entry["title"],
                "page": entry["page"],
                "section_path": entry["section_path"]
            } for entry in toc_data["toc"]],
            files=[{
                "name": f"{entry['title']}.json",
                "url": f"/api/v1/document/{doc_id}/section/{entry['section_path']}"
            } for entry in toc_data["toc"]],
            metadata=toc_data["metadata"]
        )
        
    except Exception as e:
        logger.error(f"Error processing PDF: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing PDF: {str(e)}")

@router.get("/document/{doc_id}/section/{section_path:path}")
async def get_section_content(doc_id: str, section_path: str):
    """
    Retrieve the content of a specific section by its path.
    """
    try:
        content = processor.get_section_content(doc_id, section_path)
        return JSONResponse(content={"content": content})
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Section content not found")
    except Exception as e:
        logger.error(f"Error retrieving section content: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving section content: {str(e)}")

@router.get("/document/{doc_id}/toc")
async def get_document_toc(doc_id: str):
    """
    Get the table of contents for a processed document.
    """
    try:
        # Try to get TOC from saved file first
        doc_dir = Path("data") / doc_id
        toc_file = doc_dir / "toc.json"
        
        if not toc_file.exists():
            raise HTTPException(status_code=404, detail="Document not found")
        
        toc_data = json.loads(toc_file.read_text())
        return JSONResponse(content=toc_data)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Document not found")
    except Exception as e:
        logger.error(f"Error retrieving TOC: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving TOC: {str(e)}")