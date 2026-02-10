"""
Shared test fixtures for all unit tests.
Provides mock objects, temp directories, and fake PDF data so no real PDFs are needed.
"""
import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# MockUploadFile – mimics FastAPI's UploadFile
# ---------------------------------------------------------------------------
class MockUploadFile:
    """Mock UploadFile that works with both sync and async test code."""

    def __init__(
        self,
        filename: str = "test_document.pdf",
        content_type: str = "application/pdf",
        content: bytes = b"fake-pdf-content",
    ):
        self.filename = filename
        self.content_type = content_type
        self._content = content

    async def read(self) -> bytes:
        return self._content


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_upload_file():
    """Return a factory that creates MockUploadFile instances."""
    def _factory(
        filename="test_document.pdf",
        content_type="application/pdf",
        content=b"fake-pdf-content",
    ):
        return MockUploadFile(filename=filename, content_type=content_type, content=content)
    return _factory


@pytest.fixture
def tmp_data_dir(tmp_path):
    """Provide a temporary directory for processed data."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    return data_dir


@pytest.fixture
def fake_pdf_bytes():
    """
    Generate a minimal valid single-page PDF using PyMuPDF (fitz).
    Falls back to a raw minimal PDF if fitz is not available.
    """
    try:
        import fitz
        doc = fitz.open()
        page = doc.new_page(width=612, height=792)
        page.insert_text((72, 72), "Test content for unit tests")
        pdf_bytes = doc.tobytes()
        doc.close()
        return pdf_bytes
    except Exception:
        # Minimal raw PDF (valid enough for fitz.open to parse)
        return (
            b"%PDF-1.0\n"
            b"1 0 obj<</Pages 2 0 R>>endobj\n"
            b"2 0 obj<</Kids[3 0 R]/Count 1>>endobj\n"
            b"3 0 obj<</MediaBox[0 0 612 792]>>endobj\n"
            b"trailer<</Root 1 0 R>>"
        )


@pytest.fixture
def mock_fitz_doc():
    """
    Patch ``fitz.open`` to return a controllable mock document.
    The mock supports get_toc(), metadata, page_count, and close().

    Usage in tests:
        def test_something(mock_fitz_doc):
            mock_doc = mock_fitz_doc(
                toc=[(1, "Intro", 1), (1, "Chapter 1", 3)],
                page_count=10,
            )
            # fitz.open(...) will now return mock_doc
    """
    _patcher = None
    _mock_doc = None

    def _factory(toc=None, page_count=5, metadata=None):
        nonlocal _patcher, _mock_doc
        if toc is None:
            toc = []
        if metadata is None:
            metadata = {"title": "Test", "author": "Author"}

        _mock_doc = MagicMock()
        _mock_doc.get_toc.return_value = toc
        _mock_doc.metadata = metadata
        _mock_doc.page_count = page_count
        _mock_doc.close.return_value = None

        _patcher = patch("fitz.open", return_value=_mock_doc)
        _patcher.start()
        return _mock_doc

    yield _factory

    if _patcher is not None:
        _patcher.stop()


@pytest.fixture
def mock_pymupdf4llm():
    """
    Patch ``pymupdf4llm.to_markdown`` so it returns predictable content.

    Usage:
        def test_x(mock_pymupdf4llm):
            mock_to_md = mock_pymupdf4llm("# Page content")
            # pymupdf4llm.to_markdown(...) now returns "# Page content"
    """
    _patcher = None

    def _factory(return_value="# Mocked markdown content\n\nSome text."):
        nonlocal _patcher
        _patcher = patch("pymupdf4llm.to_markdown", return_value=return_value)
        mock_fn = _patcher.start()
        return mock_fn

    yield _factory

    if _patcher is not None:
        _patcher.stop()


def write_section_file(data_dir: Path, doc_id: str, section_path: str, content: str = "Section content"):
    """Helper: write a section markdown file on disk."""
    sections_dir = data_dir / doc_id / "sections"
    sections_dir.mkdir(parents=True, exist_ok=True)
    section_file = sections_dir / f"{section_path}.md"
    section_file.write_text(content)
    return section_file


def write_toc_file(data_dir: Path, doc_id: str, entries=None, metadata=None, page_count=5):
    """Helper: write a toc.json file on disk."""
    doc_dir = data_dir / doc_id
    doc_dir.mkdir(parents=True, exist_ok=True)
    toc_data = {
        "entries": entries or [],
        "metadata": metadata or {"title": "Test"},
        "page_count": page_count,
    }
    toc_file = doc_dir / "toc.json"
    toc_file.write_text(json.dumps(toc_data, indent=2))
    return toc_file
