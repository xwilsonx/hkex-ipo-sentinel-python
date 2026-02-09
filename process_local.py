import asyncio
import os
import logging
from pathlib import Path
from pdf_processor.core.pdf_processor import PDFProcessor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class LocalFile:
    """Wrapper for local file to mimic UploadFile interface partially"""
    def __init__(self, path: Path):
        self.path = path
        self.filename = path.name
        self.content_type = "application/pdf"
        
    async def read(self):
        with open(self.path, 'rb') as f:
            return f.read()

async def process_local_files():
    # Setup paths
    base_dir = Path("pdf_processor")
    pdf_dir = base_dir / "data" / "pdf"
    
    if not pdf_dir.exists():
        logger.error(f"PDF directory not found: {pdf_dir}")
        return
        
    # Initialize processor
    # Note: data_dir is relative to where script is run, so we point to pdf_processor/data
    processor = PDFProcessor(data_dir=str(base_dir / "data"))
    
    # Find PDF files
    pdf_files = list(pdf_dir.glob("*.pdf"))
    if not pdf_files:
        logger.warning(f"No PDF files found in {pdf_dir}")
        return
        
    logger.info(f"Found {len(pdf_files)} PDF files to process")
    
    for pdf_path in pdf_files:
        try:
            # Use filename without extension as doc_id
            doc_id = pdf_path.stem
            logger.info(f"Processing {pdf_path.name} (ID: {doc_id})...")
            
            # Wrap file
            file_obj = LocalFile(pdf_path)
            
            # Process
            result = await processor.process_pdf(file_obj, doc_id)
            
            # Verify output
            output_dir = base_dir / "data" / doc_id
            if output_dir.exists():
                toc_count = len(result.get("toc", []))
                logger.info(f"Successfully processed {pdf_path.name}. Generated {toc_count} TOC entries.")
                logger.info(f"Output saved to: {output_dir}")
            else:
                logger.error(f"Processing failed to create output directory for {pdf_path.name}")
                
        except Exception as e:
            logger.error(f"Error processing {pdf_path.name}: {str(e)}")

def main():
    asyncio.run(process_local_files())

if __name__ == "__main__":
    main()
