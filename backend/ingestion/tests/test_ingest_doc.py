"""
backend/ingestion/tests/test_ingest_doc.py
TDD tests for backend/ingestion/ingest_doc.py — single-document ingest CLI.

RED phase: tests written before implementation.
All tests mock external dependencies (OpenRouter, Qdrant) to test logic only.
"""
import asyncio
import io
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# --- Test extract_pdf ---


def test_extract_pdf_returns_text(tmp_path):
    """PDF with extractable text → returns non-empty string."""
    from backend.ingestion.ingest_doc import extract_pdf

    pdf_path = tmp_path / "policy.pdf"

    # Mock fitz.open to return a document with a page
    mock_page = MagicMock()
    mock_page.get_text.return_value = "This is the policy text."
    mock_doc = MagicMock()
    mock_doc.is_encrypted = False
    mock_doc.__iter__.return_value = iter([mock_page])

    with patch("backend.ingestion.ingest_doc.fitz.open", return_value=mock_doc):
        result = extract_pdf(pdf_path)

    assert result == "This is the policy text."


def test_extract_pdf_raises_on_empty_text(tmp_path):
    """PDF with zero extractable text → raises ValueError with correct message."""
    from backend.ingestion.ingest_doc import extract_pdf

    pdf_path = tmp_path / "scanned.pdf"

    mock_page = MagicMock()
    mock_page.get_text.return_value = ""
    mock_doc = MagicMock()
    mock_doc.is_encrypted = False
    mock_doc.__iter__.return_value = iter([mock_page])

    with patch("backend.ingestion.ingest_doc.fitz.open", return_value=mock_doc):
        with pytest.raises(ValueError, match="No text extracted"):
            extract_pdf(pdf_path)


def test_extract_pdf_raises_on_encrypted(tmp_path):
    """Encrypted PDF → raises ValueError with 'PDF is encrypted' message."""
    from backend.ingestion.ingest_doc import extract_pdf

    pdf_path = tmp_path / "encrypted.pdf"

    mock_doc = MagicMock()
    mock_doc.is_encrypted = True

    with patch("backend.ingestion.ingest_doc.fitz.open", return_value=mock_doc):
        with pytest.raises(ValueError, match="PDF is encrypted"):
            extract_pdf(pdf_path)


def test_extract_pdf_joins_multiple_pages(tmp_path):
    """Multiple pages → text joined with double newline."""
    from backend.ingestion.ingest_doc import extract_pdf

    pdf_path = tmp_path / "multi.pdf"

    page1 = MagicMock()
    page1.get_text.return_value = "Page one content."
    page2 = MagicMock()
    page2.get_text.return_value = "Page two content."
    mock_doc = MagicMock()
    mock_doc.is_encrypted = False
    mock_doc.__iter__.return_value = iter([page1, page2])

    with patch("backend.ingestion.ingest_doc.fitz.open", return_value=mock_doc):
        result = extract_pdf(pdf_path)

    assert "Page one content." in result
    assert "Page two content." in result
    assert "\n\n" in result


# --- Test extract_txt ---


def test_extract_txt_reads_utf8(tmp_path):
    """TXT file with UTF-8 content → returns text."""
    from backend.ingestion.ingest_doc import extract_txt

    txt_path = tmp_path / "policy.txt"
    txt_path.write_text("Privacy policy content here.", encoding="utf-8")

    result = extract_txt(txt_path)
    assert result == "Privacy policy content here."


def test_extract_txt_fallback_latin1(tmp_path):
    """TXT file with latin-1 encoding → falls back and reads successfully."""
    from backend.ingestion.ingest_doc import extract_txt

    txt_path = tmp_path / "policy.txt"
    txt_path.write_bytes("Caf\xe9 policy.".encode("latin-1"))

    result = extract_txt(txt_path)
    assert "Caf" in result
    assert "policy" in result


def test_extract_txt_raises_on_empty(tmp_path):
    """Empty TXT file → raises ValueError with 'TXT file is empty' message."""
    from backend.ingestion.ingest_doc import extract_txt

    txt_path = tmp_path / "empty.txt"
    txt_path.write_text("", encoding="utf-8")

    with pytest.raises(ValueError, match="TXT file is empty"):
        extract_txt(txt_path)


# --- Test ingest_doc ---


@pytest.mark.asyncio
async def test_ingest_doc_unsupported_extension(tmp_path):
    """Unsupported file type → raises ValueError with 'Unsupported file type' message."""
    from backend.ingestion.ingest_doc import ingest_doc

    docx_path = tmp_path / "policy.docx"
    docx_path.write_text("some content")

    with pytest.raises(ValueError, match="Unsupported file type"):
        await ingest_doc(filepath=docx_path, title="Test Policy")


@pytest.mark.asyncio
async def test_ingest_doc_dry_run_no_upsert(tmp_path):
    """--dry-run prints count without writing to Qdrant."""
    from backend.ingestion.ingest_doc import ingest_doc

    txt_path = tmp_path / "policy.txt"
    txt_path.write_text("This is a privacy policy with enough content.", encoding="utf-8")

    mock_qdrant = AsyncMock()
    mock_qdrant.retrieve = AsyncMock(return_value=[])  # nothing already indexed

    mock_openrouter = AsyncMock()

    with patch("backend.ingestion.ingest_doc._make_clients", return_value=(mock_openrouter, mock_qdrant)):
        with patch("backend.ingestion.ingest_doc.chunk_passage") as mock_chunk:
            with patch("backend.ingestion.ingest_doc.probe_embedding_dim", return_value=2048):
                with patch("backend.ingestion.ingest_doc.ensure_collection"):
                    mock_chunk.return_value = [
                        MagicMock(passage_id="policy", chunk_index=0, text="chunk text", title="Test", source_doc="Test", token_count=5),
                    ]
                    await ingest_doc(filepath=txt_path, title="Test Policy", dry_run=True)

    # Upsert must NOT have been called
    mock_qdrant.upsert.assert_not_called()


@pytest.mark.asyncio
async def test_ingest_doc_dedup_skips_existing(tmp_path):
    """Re-run on already-indexed doc → upserts 0 new chunks."""
    from backend.ingestion.ingest_doc import ingest_doc

    txt_path = tmp_path / "policy.txt"
    txt_path.write_text("Content of already-indexed policy.", encoding="utf-8")

    # Build a UUID5 that matches what ingest_doc would compute
    chunk_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, "policy:0"))

    mock_existing_point = MagicMock()
    mock_existing_point.id = chunk_id

    mock_qdrant = AsyncMock()
    mock_qdrant.retrieve = AsyncMock(return_value=[mock_existing_point])

    mock_openrouter = AsyncMock()

    with patch("backend.ingestion.ingest_doc._make_clients", return_value=(mock_openrouter, mock_qdrant)):
        with patch("backend.ingestion.ingest_doc.chunk_passage") as mock_chunk:
            with patch("backend.ingestion.ingest_doc.probe_embedding_dim", return_value=2048):
                with patch("backend.ingestion.ingest_doc.ensure_collection"):
                    mock_chunk.return_value = [
                        MagicMock(passage_id="policy", chunk_index=0, text="chunk text", title="Test", source_doc="Test", token_count=5),
                    ]
                    await ingest_doc(filepath=txt_path, title="Test Policy", dry_run=False)

    # Upsert must NOT have been called since everything already indexed
    mock_qdrant.upsert.assert_not_called()


@pytest.mark.asyncio
async def test_ingest_doc_upserts_new_chunks(tmp_path):
    """New document → upserts chunks with correct payload including file_type."""
    from backend.ingestion.ingest_doc import ingest_doc

    txt_path = tmp_path / "policy.txt"
    txt_path.write_text("Brand new policy content.", encoding="utf-8")

    mock_qdrant = AsyncMock()
    mock_qdrant.retrieve = AsyncMock(return_value=[])  # no existing

    mock_upsert_result = MagicMock()
    from qdrant_client.models import UpdateStatus
    mock_upsert_result.status = UpdateStatus.COMPLETED
    mock_qdrant.upsert = AsyncMock(return_value=mock_upsert_result)

    mock_openrouter = AsyncMock()

    with patch("backend.ingestion.ingest_doc._make_clients", return_value=(mock_openrouter, mock_qdrant)):
        with patch("backend.ingestion.ingest_doc.chunk_passage") as mock_chunk:
            with patch("backend.ingestion.ingest_doc.probe_embedding_dim", return_value=2048):
                with patch("backend.ingestion.ingest_doc.ensure_collection"):
                    with patch("backend.ingestion.ingest_doc.embed_batch", return_value=[[0.1] * 2048]):
                        mock_chunk.return_value = [
                            MagicMock(passage_id="policy", chunk_index=0, text="chunk text", title="Test", source_doc="Test", token_count=5),
                        ]
                        await ingest_doc(filepath=txt_path, title="Test Policy", dry_run=False)

    mock_qdrant.upsert.assert_called_once()
    call_kwargs = mock_qdrant.upsert.call_args
    points = call_kwargs.kwargs.get("points", call_kwargs.args[0] if call_kwargs.args else [])
    # Handle PointStruct objects
    assert len(points) == 1
    assert points[0].payload["file_type"] == "txt"
    assert points[0].payload["title"] == "Test Policy"


# --- Test parse_args ---


def test_parse_args_requires_title():
    """Missing --title → argparse exits with error."""
    from backend.ingestion.ingest_doc import parse_args
    import sys

    with patch.object(sys, "argv", ["ingest_doc", "policy.pdf"]):
        with pytest.raises(SystemExit) as exc_info:
            parse_args()
    assert exc_info.value.code != 0


def test_parse_args_full():
    """All args provided → Namespace has correct values."""
    from backend.ingestion.ingest_doc import parse_args
    import sys

    with patch.object(sys, "argv", ["ingest_doc", "policy.pdf", "--title", "My Policy", "--dry-run"]):
        args = parse_args()

    assert args.file == Path("policy.pdf")
    assert args.title == "My Policy"
    assert args.dry_run is True
