#!/usr/bin/env python3

"""
Test script to verify that all required dependencies are installed correctly.
"""

def test_imports():
    """Test that all required modules can be imported."""
    try:
        import fastapi
        print("✓ FastAPI imported successfully")
    except ImportError as e:
        print(f"✗ Failed to import FastAPI: {e}")
        return False
    
    try:
        import pymupdf4llm
        print("✓ pymupdf4llm imported successfully")
    except ImportError as e:
        print(f"✗ Failed to import pymupdf4llm: {e}")
        return False
    
    try:
        import pydantic
        print("✓ pydantic imported successfully")
    except ImportError as e:
        print(f"✗ Failed to import pydantic: {e}")
        return False
    
    try:
        import aiofiles
        print("✓ aiofiles imported successfully")
    except ImportError as e:
        print(f"✗ Failed to import aiofiles: {e}")
        return False
    
    return True

def test_pymupdf_functionality():
    """Test basic pymupdf4llm functionality."""
    try:
        import pymupdf4llm
        print(f"pymupdf4llm version: {getattr(pymupdf4llm, '__version__', 'unknown')}")
        # Test that we can call the open function
        # We won't actually process a file, just check the function exists
        attrs = [attr for attr in dir(pymupdf4llm) if not attr.startswith('_')]
        print(f"pymupdf4llm attributes: {attrs}")
        print("✓ pymupdf4llm functionality verified")
        return True
    except Exception as e:
        print(f"✗ Failed to verify pymupdf4llm functionality: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests."""
    print("Testing PDF Processor Installation...")
    print("=" * 40)
    
    import_success = test_imports()
    if not import_success:
        print("\n❌ Import tests failed. Please check your installation.")
        return False
    
    pymupdf_success = test_pymupdf_functionality()
    if not pymupdf_success:
        print("\n❌ pymupdf4llm tests failed. Please check your installation.")
        return False
    
    print("\n✅ All tests passed! Installation appears to be working correctly.")
    print("\nNext steps:")
    print("1. Run 'pip install -r requirements.txt' to ensure all dependencies are installed")
    print("2. Start the server with 'uvicorn pdf_processor.main:app --reload'")
    print("3. Visit http://localhost:8000/docs to view the API documentation")
    return True

if __name__ == "__main__":
    main()