"""Tests for text extraction and validation tasks."""
import pytest

from dags.tasks.extract import extract_text_from_bytes, validate_text


class TestExtractText:
    def test_extract_returns_text_from_valid_pdf_bytes(self):
        # PyMuPDF can open PDFs from bytes
        # We test with a minimal valid PDF
        import fitz
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72), "Hello World from test PDF")
        pdf_bytes = doc.tobytes()
        doc.close()

        result = extract_text_from_bytes(pdf_bytes)
        assert "Hello World from test PDF" in result

    def test_extract_raises_on_empty_bytes(self):
        with pytest.raises(ValueError, match="Could not open PDF"):
            extract_text_from_bytes(b"")


class TestValidateText:
    def test_validate_passes_for_long_text(self):
        text = "A" * 200
        result = validate_text(text)
        assert result == 200  # char_count

    def test_validate_fails_for_short_text(self):
        with pytest.raises(ValueError, match="too short"):
            validate_text("Short")

    def test_validate_fails_for_whitespace_only(self):
        with pytest.raises(ValueError, match="too short"):
            validate_text("   \n\n   ")
