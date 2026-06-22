# GraphRAG Integration with Neo4j Design

## 1. Objective
Enhance the existing Qdrant-based Vector RAG pipeline with GraphRAG capabilities using Neo4j. This integration aims to improve response quality for complex, multi-hop queries by extracting schema-free entities and relationships from privacy policy documents and using them to expand the context during retrieval.

## 2. Architecture & Infrastructure
- **Graph Database**: Neo4j Aura (Cloud Managed Instance).
- **Deployment**: We will NOT deploy Neo4j via Docker Compose. The system will connect to the cloud instance.
- **Dependencies**: Add `neo4j` (Python driver) to `requirements.txt`.
- **Environment Variables**: Add the following to `.env` and `backend/app/core/config.py`:
  - `NEO4J_URI`
  - `NEO4J_USERNAME`
  - `NEO4J_PASSWORD`

## 3. Knowledge Graph Schema
The graph will bridge the vector chunks in Qdrant with extracted semantic entities.
- **`Chunk` Node**: Represents a text chunk.
  - Property: `id` (Matches the UUID/ID used in Qdrant).
- **`Entity` Node**: Extracted dynamically by the LLM (Schema-free).
  - Properties: `name` (string), `type` (string), `description` (string).
- **Relationships**:
  - `(Chunk)-[:HAS_ENTITY]->(Entity)`: Links a vector chunk to the entities mentioned within it.
  - `(Entity)-[:RELATES_TO {description: "..."}]->(Entity)`: Semantic relationships between entities extracted by the LLM.

## 4. Ingestion Pipeline (`backend/ingestion/ingest.py`)
- **Extraction**: For each processed chunk, a secondary LLM call (via OpenRouter/Gemma 4 26B) will be made. The prompt will instruct the LLM to extract a JSON list of entities and their relationships based on the chunk's text.
- **Insertion**: Extracted data will be written to Neo4j Aura using the Python driver. The `Chunk` node will be created and linked to the `Entity` nodes.
- **Resilience**: The process will reuse the existing `ingestion_checkpoint.json` mechanism to ensure that if the ingestion is interrupted (e.g., due to rate limits or network issues), it can resume without duplicating work.

## 5. Retrieval & Generation Pipeline (`backend/app/services/rag.py`)
The retrieval phase will use a Local Search (Hybrid) approach:
- **Step 1 (Vector Search)**: The user query is embedded and searched against Qdrant to retrieve the Top-K most relevant text chunks.
- **Step 2 (Graph Expansion)**: The IDs of the Top-K chunks are used to query Neo4j. The query will retrieve all `Entity` nodes connected to these chunks (`HAS_ENTITY`), as well as their 1-hop neighboring entities and relationships (`RELATES_TO`).
- **Step 3 (Context Merging)**: The graph paths (e.g., "Entity A -> [relationship description] -> Entity B") are serialized into text format.
- **Step 4 (Generation)**: The final prompt to the Answer Generation LLM will include both the original semantic text chunks (from Qdrant) and the expanded graph context (from Neo4j).
