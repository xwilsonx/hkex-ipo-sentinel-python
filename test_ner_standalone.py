import asyncio
import logging
from pdf_processor.ner.manager import NERManager

logging.basicConfig(level=logging.INFO)

async def test_ner():
    text = """
    This is a test document.
    Signed by Mr. John Doe on behalf of Acme Corp.
    Ms. Jane Smith also attended the meeting.
    """
    
    manager = NERManager(method="spacy")
    result = await manager.extractor.extract(text)
    
    print("\n--- NER Result ---")
    print(f"Names: {result.names}")
    print(f"Salutation: {result.salutation}")
    print(f"Metadata: {result.metadata}")
    
    assert "John Doe" in result.names or "Mr. John Doe" in result.names
    assert "Jane Smith" in result.names or "Ms. Jane Smith" in result.names
    print("\nTest passed successfully!")

if __name__ == "__main__":
    asyncio.run(test_ner())
