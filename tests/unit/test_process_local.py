"""
Unit tests for process_local.py (LocalFile class and process_local_files function).
All file-system and processor interactions are mocked.
"""
import asyncio
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

from process_local import LocalFile, process_local_files


# ==========================================================================
# LocalFile
# ==========================================================================
class TestLocalFile:
    def test_filename(self, tmp_path):
        p = tmp_path / "sample.pdf"
        p.write_bytes(b"pdf-bytes")
        lf = LocalFile(p)
        assert lf.filename == "sample.pdf"

    def test_content_type(self, tmp_path):
        p = tmp_path / "report.pdf"
        p.write_bytes(b"data")
        lf = LocalFile(p)
        assert lf.content_type == "application/pdf"

    @pytest.mark.asyncio
    async def test_read_returns_bytes(self, tmp_path):
        p = tmp_path / "doc.pdf"
        content = b"fake-pdf-content-here"
        p.write_bytes(content)
        lf = LocalFile(p)
        result = await lf.read()
        assert result == content

    @pytest.mark.asyncio
    async def test_read_large_file(self, tmp_path):
        p = tmp_path / "large.pdf"
        content = b"X" * 100_000
        p.write_bytes(content)
        lf = LocalFile(p)
        result = await lf.read()
        assert len(result) == 100_000


# ==========================================================================
# process_local_files
# ==========================================================================
class TestProcessLocalFiles:
    @pytest.mark.asyncio
    @patch("process_local.PDFProcessor")
    async def test_no_pdf_dir(self, MockProcessor, caplog):
        """When the pdf directory doesn't exist, should log error and return."""
        with patch("process_local.Path") as MockPathCls:
            mock_base = MagicMock()
            mock_pdf_dir = MagicMock()
            mock_pdf_dir.exists.return_value = False

            mock_base.__truediv__ = MagicMock(side_effect=lambda x: {
                "data": MagicMock(__truediv__=MagicMock(return_value=mock_pdf_dir))
            }.get(x, MagicMock()))

            MockPathCls.return_value = mock_base

            await process_local_files()
            # Function should return early without processing

    @pytest.mark.asyncio
    @patch("process_local.PDFProcessor")
    async def test_no_pdf_files_found(self, MockProcessor, tmp_path):
        """When pdf dir exists but has no PDFs, should log warning."""
        pdf_dir = tmp_path / "pdf_processor" / "data" / "pdf"
        pdf_dir.mkdir(parents=True)

        with patch("process_local.Path", return_value=tmp_path / "pdf_processor"):
            # Will look for pdf_processor/data/pdf which exists but is empty
            await process_local_files()

    @pytest.mark.asyncio
    async def test_successful_processing(self, tmp_path):
        """When PDFs are found, should process each one."""
        # Set up directory structure
        base = tmp_path / "pdf_processor"
        pdf_dir = base / "data" / "pdf"
        pdf_dir.mkdir(parents=True)

        # Create fake PDF files
        (pdf_dir / "test1.pdf").write_bytes(b"pdf1")
        (pdf_dir / "test2.pdf").write_bytes(b"pdf2")

        mock_processor = MagicMock()
        mock_processor.process_pdf = AsyncMock(return_value={"toc": [{"title": "A"}]})

        # Also need the output dir to exist for verification
        (base / "data" / "test1").mkdir(parents=True, exist_ok=True)
        (base / "data" / "test2").mkdir(parents=True, exist_ok=True)

        with patch("process_local.Path", return_value=base):
            with patch("process_local.PDFProcessor", return_value=mock_processor):
                await process_local_files()

        assert mock_processor.process_pdf.call_count == 2

    @pytest.mark.asyncio
    async def test_exception_during_processing(self, tmp_path):
        """Exception processing one file shouldn't stop others."""
        base = tmp_path / "pdf_processor"
        pdf_dir = base / "data" / "pdf"
        pdf_dir.mkdir(parents=True)

        (pdf_dir / "good.pdf").write_bytes(b"pdf")
        (pdf_dir / "bad.pdf").write_bytes(b"pdf")

        call_count = 0

        async def mock_process(file_obj, doc_id):
            nonlocal call_count
            call_count += 1
            if doc_id == "bad":
                raise Exception("Processing failed")
            return {"toc": []}

        mock_processor = MagicMock()
        mock_processor.process_pdf = mock_process

        (base / "data" / "good").mkdir(parents=True, exist_ok=True)

        with patch("process_local.Path", return_value=base):
            with patch("process_local.PDFProcessor", return_value=mock_processor):
                await process_local_files()

        assert call_count == 2  # Both were attempted
