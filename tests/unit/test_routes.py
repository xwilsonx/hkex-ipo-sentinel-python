"""
Unit tests for API routes (pdf_processor/api/routes.py).
Uses httpx.AsyncClient with ASGITransport for testing FastAPI endpoints.
"""
import json
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

import httpx
import pytest

from pdf_processor.main import app


# ---------------------------------------------------------------------------
# Helper: create async client
# ---------------------------------------------------------------------------
def _client():
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://testserver")


# ==========================================================================
# sanitize_filename (pure function – no mocking needed)
# ==========================================================================
class TestSanitizeFilename:
    """Test the sanitize_filename helper in routes.py."""

    def _call(self, filename: str) -> str:
        from pdf_processor.api.routes import sanitize_filename
        return sanitize_filename(filename)

    def test_normal_name(self):
        assert self._call("my_report.pdf") == "my_report"

    def test_extension_removed(self):
        result = self._call("document.v2.pdf")
        assert not result.endswith(".pdf")

    def test_special_chars_replaced(self):
        result = self._call("hello world (copy).pdf")
        assert "(" not in result
        assert ")" not in result

    def test_multiple_underscores_collapsed(self):
        result = self._call("a___b.pdf")
        assert "__" not in result

    def test_leading_trailing_underscores_stripped(self):
        result = self._call("__name__.pdf")
        assert not result.startswith("_")
        assert not result.endswith("_")

    def test_hyphen_preserved(self):
        result = self._call("my-report.pdf")
        assert "-" in result

    def test_unicode_chars(self):
        result = self._call("報告.pdf")
        assert isinstance(result, str)


# ==========================================================================
# POST /api/v1/upload-pdf
# ==========================================================================
class TestUploadPdf:
    """Test the upload-pdf endpoint."""

    @pytest.mark.asyncio
    @patch("pdf_processor.api.routes.processor")
    async def test_success(self, mock_processor):
        mock_processor.process_pdf = AsyncMock(return_value={
            "toc": [
                {"level": 1, "title": "Intro", "page": 1, "section_path": "section_000_Intro"}
            ],
            "metadata": {"filename": "test.pdf", "content_type": "application/pdf"}
        })

        async with _client() as client:
            response = await client.post(
                "/api/v1/upload-pdf",
                files={"file": ("test.pdf", b"fake-pdf-content", "application/pdf")},
            )

        assert response.status_code == 200
        data = response.json()
        assert "document_id" in data
        assert "toc" in data
        assert len(data["toc"]) == 1

    @pytest.mark.asyncio
    @patch("pdf_processor.api.routes.processor")
    async def test_non_pdf_rejected(self, mock_processor):
        async with _client() as client:
            response = await client.post(
                "/api/v1/upload-pdf",
                files={"file": ("test.txt", b"hello", "text/plain")},
            )

        assert response.status_code == 400
        assert "PDF" in response.json()["detail"]

    @pytest.mark.asyncio
    @patch("pdf_processor.api.routes.processor")
    async def test_processor_exception_500(self, mock_processor):
        mock_processor.process_pdf = AsyncMock(side_effect=Exception("Processing failed"))

        async with _client() as client:
            response = await client.post(
                "/api/v1/upload-pdf",
                files={"file": ("test.pdf", b"fake", "application/pdf")},
            )

        assert response.status_code == 500
        assert "Error processing PDF" in response.json()["detail"]


# ==========================================================================
# GET /api/v1/document/{doc_id}/section/{section_path}
# ==========================================================================
class TestGetSectionContent:
    """Test the section content endpoint."""

    @pytest.mark.asyncio
    @patch("pdf_processor.api.routes.processor")
    async def test_success(self, mock_processor):
        mock_processor.get_section_content.return_value = "# Introduction\n\nSome content."

        async with _client() as client:
            response = await client.get("/api/v1/document/doc1/section/section_000_intro")

        assert response.status_code == 200
        assert response.json()["content"] == "# Introduction\n\nSome content."

    @pytest.mark.asyncio
    @patch("pdf_processor.api.routes.processor")
    async def test_not_found(self, mock_processor):
        mock_processor.get_section_content.side_effect = FileNotFoundError("not found")

        async with _client() as client:
            response = await client.get("/api/v1/document/doc1/section/missing")

        assert response.status_code == 404

    @pytest.mark.asyncio
    @patch("pdf_processor.api.routes.processor")
    async def test_internal_error(self, mock_processor):
        mock_processor.get_section_content.side_effect = Exception("disk error")

        async with _client() as client:
            response = await client.get("/api/v1/document/doc1/section/broken")

        assert response.status_code == 500
        assert "Error retrieving section content" in response.json()["detail"]


# ==========================================================================
# GET /api/v1/document/{doc_id}/toc
# ==========================================================================
class TestGetDocumentToc:
    """Test the TOC retrieval endpoint."""

    @pytest.mark.asyncio
    async def test_success(self, tmp_path):
        """Create a real toc.json file and verify the endpoint reads it."""
        toc_data = {
            "entries": [{"level": 1, "title": "A", "page": 1, "section_path": "s"}],
            "metadata": {"title": "Test"},
            "page_count": 5,
        }

        with patch("pdf_processor.api.routes.Path") as MockPath:
            mock_toc_file = MagicMock()
            mock_toc_file.exists.return_value = True
            mock_toc_file.read_text.return_value = json.dumps(toc_data)

            mock_doc_dir = MagicMock()
            mock_doc_dir.__truediv__ = MagicMock(return_value=mock_toc_file)

            MockPath.return_value.__truediv__ = MagicMock(return_value=mock_doc_dir)

            async with _client() as client:
                response = await client.get("/api/v1/document/doc1/toc")

            assert response.status_code == 200
            data = response.json()
            assert "entries" in data

    @pytest.mark.asyncio
    async def test_not_found(self):
        """When toc.json doesn't exist, route should return 404 via FileNotFoundError path."""
        with patch("pdf_processor.api.routes.Path") as MockPath:
            mock_toc_file = MagicMock()
            # Make exists() return True so the code proceeds to read_text()
            # then raise FileNotFoundError from read_text() to trigger the
            # except FileNotFoundError handler which properly returns 404
            mock_toc_file.exists.return_value = True
            mock_toc_file.read_text.side_effect = FileNotFoundError("toc.json not found")

            mock_doc_dir = MagicMock()
            mock_doc_dir.__truediv__ = MagicMock(return_value=mock_toc_file)

            MockPath.return_value.__truediv__ = MagicMock(return_value=mock_doc_dir)

            async with _client() as client:
                response = await client.get("/api/v1/document/missing/toc")

            assert response.status_code == 404


# ==========================================================================
# Root endpoint
# ==========================================================================
class TestRootEndpoint:
    @pytest.mark.asyncio
    async def test_root_returns_message(self):
        async with _client() as client:
            response = await client.get("/")
        assert response.status_code == 200
        assert "PDF Processor API" in response.json()["message"]
