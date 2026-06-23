# Design Spec: Personal Document Ingestion via Cloud Airflow

## 1. Overview
Allow users to upload personal PDF documents, process them via Cloud Composer (Airflow) for heavy OCR and text cleaning, and securely ingest them into both Qdrant (Vector DB) and Neo4j (Graph DB) while ensuring strict data isolation per user.

## 2. Architecture & Data Flow
To keep the local Docker Compose environment lightweight and avoid exposing internal ports to the internet, we use a **Cloud Airflow + Local Polling** architecture.

1. **Upload & Trigger:**
   - User uploads a PDF via Frontend.
   - FastAPI Backend (`POST /api/documents/upload`) uploads the PDF to Google Cloud Storage (GCS).
   - FastAPI triggers an Airflow DAG on Cloud Composer via REST API, passing the GCS URI and `user_id`.
   - FastAPI creates a `Document` record in SQL with status `processing` and the Airflow `task_id`.

2. **Cloud Processing (Airflow DAG):**
   - **Task 1:** Download PDF from GCS.
   - **Task 2:** Run advanced OCR and Layout parsing.
   - **Task 3:** Text cleaning and metadata extraction.
   - **Task 4:** Chunking and Graph Extraction (identify entities/relationships).
   - **Task 5:** Upload processed JSON (chunks, graph nodes/edges) back to GCS.

3. **Local Polling & Ingestion (FastAPI Background Task):**
   - FastAPI periodically polls Airflow (or checks GCS) for task completion.
   - Once complete, FastAPI downloads the processed JSON.
   - FastAPI calls OpenRouter to generate embeddings for the chunks.
   - FastAPI upserts vectors into **Qdrant** and graph data into **Neo4j**.
   - Updates `Document` status to `completed` or `failed`.

## 3. Data Model & Security (Data Isolation)
Strict tenant isolation is required so users cannot query each other's private documents.

### SQL Database
- **`documents` table:**
  - Add `user_id` (ForeignKey to `users`).
  - Add `gcs_path` (string) for temporary storage location.
  - Add `task_id` (string) for Airflow tracking.

### Qdrant (Vector DB)
- **Schema:** Keep using the existing `policies` collection.
- **Payload:** Append `user_id` to every point's payload.
- **Retrieval:** Update the search filter to always include `WHERE user_id = current_user.id OR user_id = 'system'`.

### Neo4j (Graph DB)
- **Schema:** Update `upsert_graph_to_neo4j`.
- **Nodes:** Both `Chunk` and `Entity` nodes MUST include a `user_id` property.
  - e.g., `MERGE (e:Entity {name: $name, user_id: $user_id})`
  - This prevents an entity named "Contract" from User A merging with "Contract" from User B.
- **Relationships:** Inherently isolated if the source/target entities are isolated.
- **Retrieval:** Update GraphRAG Cypher queries to match `user_id = current_user.id OR user_id = 'system'`.

## 4. API Endpoints
- **`POST /api/documents/upload`**: Accepts `UploadFile` (PDF), uploads to GCS, triggers DAG, returns Document ID.
- **`GET /api/documents`**: Returns a list of documents owned by the `current_user`.
- **`GET /api/documents/{id}/status`**: Returns current processing status.

## 5. Self-Review & Open Questions
- **Scope check:** Is the project well scoped? Yes, we are defining the bridge between FastAPI, GCS, Airflow, Qdrant, and Neo4j.
- **Ambiguity check:** OpenRouter API is called locally (in FastAPI) to avoid passing API keys to Cloud Airflow. The heavy text processing stays on Airflow.
