
import asyncio
from fastapi.testclient import TestClient
from pdf_processor.main import app
from pathlib import Path
import shutil

# Create a dummy PDF file for testing
def create_dummy_pdf(filename):
    from fpdf import FPDF
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt="Welcome to Python!", ln=1, align="C")
    pdf.output(filename)

def test_upload_pdf_filename_usage():
    client = TestClient(app)
    
    # Setup
    pdf_filename = "test_document_v2.pdf"
    create_dummy_pdf(pdf_filename)
    
    try:
        # cleanup before test
        expected_dir = Path("data") / "test_document_v2"
        if expected_dir.exists():
            shutil.rmtree(expected_dir)

        # Update
        with open(pdf_filename, "rb") as f:
            response = client.post(
                "/api/v1/upload-pdf",
                files={"file": (pdf_filename, f, "application/pdf")}
            )
            
        assert response.status_code == 200
        data = response.json()
        assert data["document_id"] == "test_document_v2"
        
        # Verify directory exists
        assert expected_dir.exists()
        assert (expected_dir / "toc.json").exists()
        
        print("Verification Successful: Directory created with filename!")
        
    finally:
        # Cleanup
        if Path(pdf_filename).exists():
            Path(pdf_filename).unlink()

if __name__ == "__main__":
    test_upload_pdf_filename_usage()
