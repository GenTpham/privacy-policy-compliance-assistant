import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from pathlib import Path

from backend.app.db.models import Document
from backend.app.services.document_processor import process_document_inline

@pytest.fixture
def mock_document():
    doc = Document(
        id=1,
        user_id=123,
        title="Test Document",
        status="processing",
        chunk_count=0
    )
    return doc

@pytest.fixture
def mock_chunk():
    chunk = MagicMock()
    chunk.text = "chunk text"
    chunk.passage_id = "1"
    chunk.chunk_index = 0
    chunk.token_count = 10
    return chunk

@pytest.mark.asyncio
async def test_process_document_inline_success(mock_document, mock_chunk):
    mock_session = AsyncMock()
    mock_session.get.return_value = mock_document
    
    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__.return_value = mock_session
    
    with patch("backend.app.services.document_processor._session_factory", mock_session_factory), \
         patch("backend.app.services.document_processor.tempfile.NamedTemporaryFile") as mock_temp, \
         patch("backend.app.services.document_processor.os.remove") as mock_remove:
             
        mock_temp.return_value.__enter__.return_value.name = "test.pdf"
        
        with patch("backend.app.services.document_processor.extract_pdf", return_value="full text") as mock_extract, \
             patch("backend.app.services.document_processor.chunk_passage", return_value=[mock_chunk]) as mock_chunk_fn, \
             patch("backend.app.services.document_processor.Neo4jClient") as mock_neo4j_client_class, \
             patch("backend.app.services.document_processor.openrouter") as mock_openrouter, \
             patch("backend.app.services.document_processor.qdrant") as mock_qdrant:
                 
            mock_neo4j = MagicMock()
            mock_neo4j_client_class.return_value = mock_neo4j
            
            mock_embed_resp = MagicMock()
            mock_embed_resp.data = [MagicMock(embedding=[0.1, 0.2, 0.3])]
            mock_openrouter.embeddings.create = AsyncMock(return_value=mock_embed_resp)
            mock_qdrant.upsert = AsyncMock()
            
            await process_document_inline(1, b"pdf data", "test.pdf")
            
            assert mock_session.get.call_count == 2
            mock_extract.assert_called_once()
            mock_chunk_fn.assert_called_once()
            mock_openrouter.embeddings.create.assert_called_once()
            mock_neo4j.execute_query.assert_called_once()
            mock_qdrant.upsert.assert_called_once()
            
            assert mock_document.status == 'success'
            assert mock_document.chunk_count == 1
            mock_session.commit.assert_called_once()
            mock_remove.assert_called_once()

@pytest.mark.asyncio
async def test_process_document_inline_unsupported_type(mock_document):
    mock_session = AsyncMock()
    mock_session.get.return_value = mock_document
    
    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__.return_value = mock_session
    
    with patch("backend.app.services.document_processor.db_session._session_factory", mock_session_factory):
        await process_document_inline(1, b"data", "test.xyz")
        assert mock_document.status == 'failed'

@pytest.mark.asyncio
async def test_process_document_inline_extraction_error(mock_document):
    mock_session = AsyncMock()
    mock_session.get.return_value = mock_document
    
    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__.return_value = mock_session
    
    with patch("backend.app.services.document_processor._session_factory", mock_session_factory), \
         patch("backend.app.services.document_processor.tempfile.NamedTemporaryFile") as mock_temp, \
         patch("backend.app.services.document_processor.os.remove"):
             
        mock_temp.return_value.__enter__.return_value.name = "test.pdf"
        
        with patch("backend.app.services.document_processor.extract_pdf", side_effect=Exception("Extraction Error")):
            await process_document_inline(1, b"pdf data", "test.pdf")
            assert mock_document.status == 'failed'
