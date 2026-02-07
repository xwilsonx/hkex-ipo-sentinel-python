# PDF Processor API

A high-performance Python application for processing PDF documents and extracting structured content for LLM integration.

## Features

- RESTful API built with FastAPI
- PDF Table of Contents extraction
- Section content stored in separate files for performance
- LLM-ready content formatting using pymupdf4llm
- Asynchronous processing for non-blocking operations

## Project Structure

```
pdf_processor/
├── api/              # API routes and request handlers
├── core/             # Core business logic and PDF processing
├── models/           # Data models and schemas
├── data/             # Processed document storage (created at runtime)
├── main.py           # Application entry point
└── requirements.txt  # Python dependencies
```

## Installation

### Option 1: Direct Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run the application:
```bash
uvicorn pdf_processor.main:app --reload
```

Or:
```bash
python -m pdf_processor.main
```

### Option 2: Using Docker

1. Build and run with Docker:
```bash
docker-compose up --build
```

2. Or build and run with Docker directly:
```bash
docker build -t pdf-processor .
docker run -p 8000:8000 -v $(pwd)/data:/app/data pdf-processor
```

## API Endpoints

### Upload PDF
```
POST /api/v1/upload-pdf
```
Upload a PDF file and extract its table of contents. Section content is saved to separate files.

### Get Document TOC
```
GET /api/v1/document/{doc_id}/toc
```
Retrieve the table of contents for a processed document.

### Get Section Content
```
GET /api/v1/document/{doc_id}/section/{section_path}
```
Retrieve the content of a specific section by its path.

## Performance Considerations

- Large PDFs (up to 200 pages) are processed efficiently using pymupdf4llm
- Section content is stored in separate files rather than in memory
- Asynchronous file operations prevent blocking
- Temporary files are cleaned up after processing