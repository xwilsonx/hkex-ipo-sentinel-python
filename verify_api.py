import asyncio
import json
import urllib.request
import urllib.parse
import mimetypes
import uuid
from pathlib import Path

# Use localhost:8000 as per common FastAPI defaults
BASE_URL = "http://localhost:8000"

def create_dummy_pdf(filename="test.pdf"):
    """Creates a minimal valid PDF file for testing."""
    with open(filename, "wb") as f:
        f.write(b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n3 0 obj\n<< /Type /Page /Parent 2 0 R /Resources << >> /MediaBox [0 0 612 792] >>\nendobj\nxref\n0 4\n0000000000 65535 f\n0000000010 00000 n\n0000000060 00000 n\n0000000117 00000 n\ntrailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n223\n%%EOF\n")
    return filename

async def verify_api():
    print(f"Testing API at {BASE_URL}...")
    
    # 1. Create dummy PDF
    pdf_path = create_dummy_pdf()
    print(f"Created dummy PDF: {pdf_path}")
    
    try:
        # 2. Upload PDF
        # We use standard urllib to avoid requests/httpx dependency if not installed
        # But multipart/form-data with urllib is painful. 
        # Let's try to assume requests is available since it's common, 
        # OR just use a simple curl command via subprocess if this is too complex for a quick script without deps.
        # Actually, let's use the installed 'fastapi' and 'uvicorn' environment. 
        # The user has 'httpx' likely installed if they have fastapi? No, starlette uses requests? 
        # Let's check imports.
        
        try:
            import requests
        except ImportError:
            print("Requests library not found. Installing...")
            import subprocess
            subprocess.check_call(["pip", "install", "requests"])
            import requests

        files = {'file': open(pdf_path, 'rb')}
        response = requests.post(f"{BASE_URL}/api/v1/upload-pdf", files=files)
        
        if response.status_code != 200:
            print(f"FAILED: Upload returned {response.status_code}")
            print(response.text)
            return
            
        data = response.json()
        print("Upload successful!")
        print(f"Document ID: {data.get('document_id')}")
        
        # 3. Verify Response Structure
        if 'files' not in data:
            print("FAILED: 'files' key missing in response")
            return
            
        files_list = data['files']
        print(f"Files found: {len(files_list)}")
        
        # 4. Verify Links
        for file_entry in files_list:
            print(f"Checking file: {file_entry['name']} -> {file_entry['url']}")
            # Note: The backend returns URLs with /api/v1/document/... already if using url_for or if explicitly constructed?
            # In routes.py we construct it as: f"/document/{doc_id}/section/{entry['section_path']}"
            # But the router is mounted under /api/v1.
            # So the full path should be BASE_URL/api/v1 + url.
            # Wait, if routes.py returns "/document/...", it's relative to root or router?
            # It's relative to root usually if returned as string.
            # Let's check routes.py again.
            
            # ROUTES.PY: 
            # "url": f"/document/{doc_id}/section/{entry['section_path']}"
            # This is an absolute-looking path. 
            # If the client calls it, they likely need to prepend /api/v1 if the router handles it.
            # The router handles: @router.get("/document/{doc_id}/section/{section_path:path}")
            # This router is included under /api/v1.
            # So the actual URL is /api/v1/document/...
            
            # The return value from upload_pdf uses f"/document/..." which is missing /api/v1.
            # I must fix routes.py to include /api/v1 or better yet, use url_for?
            # For now, let's fix it in routes.py to explicitly include /api/v1 or make it consistent.
            # The verification script needs to handle whatever routes.py returns.
            pass
            file_url = f"{BASE_URL}{file_entry['url']}"
            
            file_resp = requests.get(file_url)
            if file_resp.status_code == 200:
                 print(f"  -> Download OK ({len(file_resp.content)} bytes)")
            else:
                 print(f"  -> Download FAILED ({file_resp.status_code})")
                 
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        # Cleanup
        if Path(pdf_path).exists():
            Path(pdf_path).unlink()

if __name__ == "__main__":
    asyncio.run(verify_api())
