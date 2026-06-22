# GraphRAG Neo4j Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enhance the existing Qdrant-based vector RAG pipeline with GraphRAG capabilities using Neo4j Aura to improve responses for complex, multi-hop queries.

**Architecture:** We will connect to Neo4j Aura (Cloud) using the official `neo4j` Python driver. During ingestion, an LLM extracts entities and relationships which are stored in Neo4j. During retrieval, we query Qdrant for semantic chunks, then query Neo4j for 1-hop graph expansion of those chunks, combining both into the final LLM context.

**Tech Stack:** Python 3.11, FastAPI, Neo4j Python Driver, OpenRouter (Gemma 4 26B), Qdrant, pytest

---

### Task 1: Configuration and Dependencies

**Files:**
- Modify: `requirements.txt`
- Modify: `backend/app/core/config.py`
- Modify: `.env.example`
- Test: `backend/app/tests/test_config_neo4j.py` (Create)

- [ ] **Step 1: Write the failing test for configuration**

```python
# backend/app/tests/test_config_neo4j.py
import os
from backend.app.core.config import settings

def test_neo4j_settings_exist():
    assert hasattr(settings, "NEO4J_URI")
    assert hasattr(settings, "NEO4J_USERNAME")
    assert hasattr(settings, "NEO4J_PASSWORD")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/app/tests/test_config_neo4j.py -v`
Expected: FAIL with `AssertionError: assert False` (or attribute error).

- [ ] **Step 3: Write minimal implementation**

Modify `requirements.txt`:
```text
# Add to the bottom
neo4j==5.21.0
```

Modify `.env.example`:
```text
# Add to the bottom
NEO4J_URI=neo4j+s://your-instance.databases.neo4j.io
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_password
```

Modify `backend/app/core/config.py`:
```python
# Add to the BaseSettings class (e.g. Settings)
class Settings(BaseSettings):
    # ... existing settings ...
    NEO4J_URI: str = "neo4j+s://localhost:7687"
    NEO4J_USERNAME: str = "neo4j"
    NEO4J_PASSWORD: str = "password"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/app/tests/test_config_neo4j.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add requirements.txt .env.example backend/app/core/config.py backend/app/tests/test_config_neo4j.py
git commit -m "feat: add neo4j dependencies and config"
```

---

### Task 2: Neo4j Connection Manager

**Files:**
- Create: `backend/app/db/neo4j_client.py`
- Create: `backend/app/tests/test_neo4j_client.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/app/tests/test_neo4j_client.py
from unittest.mock import patch
from backend.app.db.neo4j_client import Neo4jClient

@patch('neo4j.GraphDatabase.driver')
def test_neo4j_client_singleton(mock_driver):
    client1 = Neo4jClient()
    client2 = Neo4jClient()
    assert client1 is client2
    assert mock_driver.call_count == 1
    
    # Test execute query
    client1.execute_query("RETURN 1")
    client1.driver.session.return_value.__enter__.return_value.run.assert_called_with("RETURN 1", {})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/app/tests/test_neo4j_client.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.app.db.neo4j_client'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/db/neo4j_client.py
from neo4j import GraphDatabase
from backend.app.core.config import settings

class Neo4jClient:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Neo4jClient, cls).__new__(cls)
            cls._instance.driver = GraphDatabase.driver(
                settings.NEO4J_URI, 
                auth=(settings.NEO4J_USERNAME, settings.NEO4J_PASSWORD)
            )
        return cls._instance

    def execute_query(self, query: str, parameters: dict = None):
        parameters = parameters or {}
        with self.driver.session() as session:
            result = session.run(query, parameters)
            return [record.data() for record in result]
            
    def close(self):
        if self.driver:
            self.driver.close()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/app/tests/test_neo4j_client.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/db/neo4j_client.py backend/app/tests/test_neo4j_client.py
git commit -m "feat: implement neo4j connection manager"
```

---

### Task 3: Graph Extractor (LLM Entity/Relation Extraction)

**Files:**
- Create: `backend/ingestion/graph_extractor.py`
- Create: `backend/ingestion/tests/test_graph_extractor.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/ingestion/tests/test_graph_extractor.py
import json
from unittest.mock import patch, MagicMock
from backend.ingestion.graph_extractor import extract_graph_from_chunk

@patch('backend.ingestion.graph_extractor.client.chat.completions.create')
def test_extract_graph_from_chunk(mock_create):
    # Mock LLM response
    mock_response = MagicMock()
    mock_response.choices[0].message.content = json.dumps({
        "entities": [{"name": "User", "type": "Actor", "description": "A person"}],
        "relationships": [{"source": "User", "target": "System", "type": "USES", "description": "Interacts with"}]
    })
    mock_create.return_value = mock_response

    result = extract_graph_from_chunk("The user uses the system.")
    
    assert "entities" in result
    assert "relationships" in result
    assert result["entities"][0]["name"] == "User"
    assert result["relationships"][0]["type"] == "USES"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/ingestion/tests/test_graph_extractor.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.ingestion.graph_extractor'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/ingestion/graph_extractor.py
import json
import os
from openai import OpenAI
from backend.app.core.config import settings

# Initialize OpenRouter client (assuming standard setup)
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ.get("OPENROUTER_API_KEY", "dummy")
)

EXTRACTION_PROMPT = """
You are an expert at extracting Knowledge Graphs from privacy policies.
Given the text chunk, extract entities and their relationships.
Output ONLY a valid JSON object with this schema:
{
  "entities": [{"name": "entity_name", "type": "Entity_Type", "description": "Short description"}],
  "relationships": [{"source": "entity_name", "target": "target_name", "type": "RELATION_TYPE", "description": "Reason for relation"}]
}
Text:
{text}
"""

def extract_graph_from_chunk(text: str) -> dict:
    prompt = EXTRACTION_PROMPT.format(text=text)
    
    response = client.chat.completions.create(
        model="google/gemma-4-26b-a4b", # OpenRouter specific model
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0.1
    )
    
    content = response.choices[0].message.content
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {"entities": [], "relationships": []}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/ingestion/tests/test_graph_extractor.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/ingestion/graph_extractor.py backend/ingestion/tests/test_graph_extractor.py
git commit -m "feat: implement graph extractor via LLM"
```

---

### Task 4: Integrate Graph Ingestion into existing pipeline

**Files:**
- Create: `backend/ingestion/neo4j_writer.py`
- Modify: `backend/ingestion/ingest.py`
- Create: `backend/ingestion/tests/test_neo4j_writer.py`

- [ ] **Step 1: Write the failing test for neo4j_writer**

```python
# backend/ingestion/tests/test_neo4j_writer.py
from unittest.mock import MagicMock
from backend.ingestion.neo4j_writer import write_chunk_graph

def test_write_chunk_graph():
    mock_client = MagicMock()
    graph_data = {
        "entities": [{"name": "A", "type": "T", "description": "D"}],
        "relationships": [{"source": "A", "target": "B", "type": "R", "description": "D2"}]
    }
    write_chunk_graph(mock_client, "chunk123", graph_data)
    
    # Should call execute_query multiple times (for chunk, entities, relations)
    assert mock_client.execute_query.call_count >= 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/ingestion/tests/test_neo4j_writer.py -v`
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

```python
# backend/ingestion/neo4j_writer.py
from backend.app.db.neo4j_client import Neo4jClient

def write_chunk_graph(neo_client: Neo4jClient, chunk_id: str, graph_data: dict):
    # 1. Create Chunk node
    neo_client.execute_query(
        "MERGE (c:Chunk {id: $chunk_id})",
        {"chunk_id": chunk_id}
    )
    
    # 2. Create Entities and HAS_ENTITY relation
    for ent in graph_data.get("entities", []):
        neo_client.execute_query(
            """
            MERGE (e:Entity {name: $name})
            SET e.type = $type, e.description = $desc
            WITH e
            MATCH (c:Chunk {id: $chunk_id})
            MERGE (c)-[:HAS_ENTITY]->(e)
            """,
            {"name": ent["name"], "type": ent["type"], "desc": ent["description"], "chunk_id": chunk_id}
        )
        
    # 3. Create Relations
    for rel in graph_data.get("relationships", []):
        neo_client.execute_query(
            """
            MATCH (s:Entity {name: $source})
            MATCH (t:Entity {name: $target})
            MERGE (s)-[r:RELATES_TO {type: $rel_type}]->(t)
            SET r.description = $desc
            """,
            {"source": rel["source"], "target": rel["target"], "rel_type": rel["type"], "desc": rel["description"]}
        )
```

Also modify `backend/ingestion/ingest.py` (assuming there's a loop over chunks):
```python
# In backend/ingestion/ingest.py
# (Find where the chunk is inserted into Qdrant, and add graph ingestion)
# Example modification (to be adapted to actual file structure):
from backend.app.db.neo4j_client import Neo4jClient
from backend.ingestion.graph_extractor import extract_graph_from_chunk
from backend.ingestion.neo4j_writer import write_chunk_graph

# Inside main ingestion loop, after Qdrant insert:
# neo_client = Neo4jClient()
# graph_data = extract_graph_from_chunk(chunk_text)
# write_chunk_graph(neo_client, chunk_id, graph_data)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/ingestion/tests/test_neo4j_writer.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/ingestion/neo4j_writer.py backend/ingestion/ingest.py backend/ingestion/tests/test_neo4j_writer.py
git commit -m "feat: integrate graph ingestion and neo4j writer"
```

---

### Task 5: Graph Context Retrieval in RAG

**Files:**
- Create: `backend/app/services/graph_retriever.py`
- Modify: `backend/app/services/rag.py`
- Create: `backend/app/tests/test_graph_retriever.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/app/tests/test_graph_retriever.py
from unittest.mock import MagicMock
from backend.app.services.graph_retriever import get_graph_context

def test_get_graph_context():
    mock_client = MagicMock()
    mock_client.execute_query.return_value = [
        {"source": "User", "rel": "USES", "target": "System", "desc": "Interacts"}
    ]
    
    context = get_graph_context(mock_client, ["chunk_1"])
    assert "User -[USES]-> System (Interacts)" in context
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/app/tests/test_graph_retriever.py -v`
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/services/graph_retriever.py
from backend.app.db.neo4j_client import Neo4jClient

def get_graph_context(neo_client: Neo4jClient, chunk_ids: list[str]) -> str:
    if not chunk_ids:
        return ""
        
    query = """
    MATCH (c:Chunk)-[:HAS_ENTITY]->(e1:Entity)-[r:RELATES_TO]-(e2:Entity)
    WHERE c.id IN $chunk_ids
    RETURN e1.name AS source, r.type AS rel, e2.name AS target, r.description AS desc
    LIMIT 50
    """
    
    results = neo_client.execute_query(query, {"chunk_ids": chunk_ids})
    
    context_lines = []
    for row in results:
        context_lines.append(f"{row['source']} -[{row['rel']}]-> {row['target']} ({row['desc']})")
        
    return "\n".join(set(context_lines))
```

Modify `backend/app/services/rag.py`:
```python
# Inside rag.py where context is built
from backend.app.services.graph_retriever import get_graph_context
from backend.app.db.neo4j_client import Neo4jClient

# After getting Qdrant chunks:
# chunk_ids = [hit.id for hit in qdrant_results]
# neo_client = Neo4jClient()
# graph_context = get_graph_context(neo_client, chunk_ids)
# 
# Combine textual context with graph_context before sending to LLM.
# combined_context = f"Semantic Context:\n{text_context}\n\nGraph Context:\n{graph_context}"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/app/tests/test_graph_retriever.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/graph_retriever.py backend/app/services/rag.py backend/app/tests/test_graph_retriever.py
git commit -m "feat: add graph context retrieval to RAG pipeline"
```
