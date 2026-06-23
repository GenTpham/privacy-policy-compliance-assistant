import asyncio
import logging
from uuid import uuid4
import tempfile
from pathlib import Path
import os

from fastapi.concurrency import run_in_threadpool
from qdrant_client.models import PointStruct

from backend.app.db import session as db_session
from backend.app.db.models import Document
from backend.app.services.rag import qdrant, openrouter, EMBEDDING_MODEL, COLLECTION_NAME
from backend.app.db.neo4j_client import Neo4jClient
from backend.ingestion.ingest_doc import extract_pdf, extract_txt, embed_batch
from backend.ingestion.chunker import chunk_passage

logger = logging.getLogger(__name__)

async def process_document_inline(document_id: int, file_bytes: bytes, filename: str):
    if db_session._session_factory is None:
        raise RuntimeError("DB session factory not initialized")

    async with db_session._session_factory() as session:
        doc = await session.get(Document, document_id)
        if not doc:
            logger.error(f"Document {document_id} not found")
            return
        title = doc.title
        user_id = doc.user_id

    suffix = Path(filename).suffix.lower()
    if suffix not in [".pdf", ".txt"]:
        logger.error(f"Unsupported file type: {suffix}")
        await _update_status(document_id, "failed")
        return

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
        temp_file.write(file_bytes)
        temp_path = Path(temp_file.name)

    try:
        # Step 1: Extracting text
        await _update_status(document_id, "extracting_text")
        if suffix == ".pdf":
            text = await run_in_threadpool(extract_pdf, temp_path)
        else:
            text = await run_in_threadpool(extract_txt, temp_path)

        # Save extracted text to a file for manual verification/debugging
        debug_path = Path("backend/data") / f"doc_{document_id}_{Path(filename).stem}_extracted.txt"
        debug_path.parent.mkdir(parents=True, exist_ok=True)
        debug_path.write_text(text, encoding="utf-8")
        logger.info(f"Saved extracted text to {debug_path}")

        # Step 2: Chunking
        await _update_status(document_id, "chunking_text")
        passage_id = str(document_id)
        chunks = chunk_passage(text, passage_id=passage_id, title=title, source_doc=title)

        # Step 3: Embedding and Upserting (Batched)
        await _update_status(document_id, "embedding_and_saving")
        neo4j = Neo4jClient()
        points = []
        
        # We process in batches of 50 to avoid rate limits
        BATCH_SIZE = 50
        total = len(chunks)
        
        for batch_start in range(0, total, BATCH_SIZE):
            batch_chunks = chunks[batch_start: batch_start + BATCH_SIZE]
            
            # Embed the whole batch
            embeddings = await embed_batch(openrouter, [c.text for c in batch_chunks])
            
            for chunk, embedding in zip(batch_chunks, embeddings):
                point_id = str(uuid4())
                points.append(
                    PointStruct(
                        id=point_id,
                        vector=embedding,
                        payload={
                            "title": title, 
                            "source_doc": title,
                            "passage_id": passage_id,
                            "text": chunk.text, 
                            "chunk_index": chunk.chunk_index,
                            "token_count": chunk.token_count,
                            "document_id": document_id,
                            "user_id": str(user_id)
                        }
                    )
                )
                
                query = """
                MERGE (d:Document {id: $doc_id, title: $title})
                MERGE (c:Chunk {id: $chunk_id, user_id: $user_id})
                SET c.text = $text
                MERGE (d)-[:HAS_CHUNK]->(c)
                """
                await run_in_threadpool(
                    neo4j.execute_query, 
                    query, 
                    {
                        "doc_id": document_id, 
                        "title": title, 
                        "chunk_id": point_id, 
                        "text": chunk.text,
                        "user_id": str(user_id)
                    }
                )
                
        if points:
            await qdrant.upsert(
                collection_name=COLLECTION_NAME,
                points=points
            )
        
        # Step 4: Success
        async with db_session._session_factory() as session:
            doc = await session.get(Document, document_id)
            if doc:
                doc.status = 'success'
                doc.chunk_count = len(chunks)
                await session.commit()
        
    except Exception as e:
        logger.error(f"Error processing document {document_id}: {e}")
        await _update_status(document_id, "failed")
    finally:
        # Cleanup temp file
        if temp_path.exists():
            os.remove(temp_path)

async def _update_status(document_id: int, status: str):
    try:
        async with db_session._session_factory() as session:
            doc = await session.get(Document, document_id)
            if doc:
                doc.status = status
                await session.commit()
    except Exception as e:
        logger.error(f"Failed to update status for {document_id}: {e}")
