import asyncio
import os
import logging
import aiofiles
from pathlib import Path
from pdf_processor.core.pdf_processor import PDFProcessor
from pdf_processor.ner.manager import NERManager

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
    
    # Initialize NER Manager (choose 'spacy', 'local', or 'cloud')
    # For now, default to 'spacy' or read from env.
    ner_method = os.getenv("NER_METHOD", "spacy")
    ner_manager = NERManager(method=ner_method)
    
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
    
    ner_tasks = []

    for pdf_path in pdf_files:
        try:
            # Use filename without extension as doc_id
            doc_id = pdf_path.stem
            logger.info(f"Processing {pdf_path.name} (ID: {doc_id})...")
            
            # Wrap file
            file_obj = LocalFile(pdf_path)
            
            # Process PDF extraction first (awaiting this part as it's the prerequisite)
            result = await processor.process_pdf(file_obj, doc_id)
            
            # Verify output
            output_dir = base_dir / "data" / doc_id
            if output_dir.exists():
                toc_count = len(result.get("toc", []))
                logger.info(f"Successfully processed {pdf_path.name}. Generated {toc_count} TOC entries.")
                logger.info(f"Output saved to: {output_dir}")
                
                # --- START ASYNC NER EXTRACTION ---
                # We need the full text. Assuming 'text.md' or similar exists in output_dir
                # OR we use the text from 'result' if available. 
                # Let's try to read the full markdown text extracted.
                
                # Attempt to find the markdown file
                md_files = list(output_dir.glob("*.md"))
                full_text = ""
                
                # Check for sections directory
                sections_dir = output_dir / "sections"
                if sections_dir.exists():
                     section_files = sorted(list(sections_dir.glob("*.md")))
                     if section_files:
                         logger.info(f"Found {len(section_files)} section files. Aggregating...")
                         for sec in section_files:
                             async with aiofiles.open(sec, mode='r', encoding='utf-8') as f:
                                 content = await f.read()
                                 full_text += f"\n\n--- {sec.name} ---\n\n{content}"
                
                # Fallback to root files if no sections or empty
                if not full_text and md_files:
                    # Preference: {doc_id}.md, else take the first one
                    main_md = next((f for f in md_files if f.name.lower() == f"{doc_id}.md".lower()), md_files[0])
                    async with aiofiles.open(main_md, mode='r', encoding='utf-8') as f:
                        full_text = await f.read()

                if full_text:
                    # Schedule NER task independently
                    task = asyncio.create_task(ner_manager.process_and_save(full_text, output_dir))
                    ner_tasks.append(task)
                else:
                    logger.warning(f"No text content found for {doc_id}, skipping NER.")

            else:
                logger.error(f"Processing failed to create output directory for {pdf_path.name}")
                
        except Exception as e:
            logger.error(f"Error processing {pdf_path.name}: {str(e)}")

    # Wait for all NER tasks to complete before exiting
    if ner_tasks:
        logger.info(f"Waiting for {len(ner_tasks)} background NER tasks to complete...")
        await asyncio.gather(*ner_tasks)
    
    logger.info("All processing complete.")

def main():
    asyncio.run(process_local_files())

if __name__ == "__main__":
    main()
