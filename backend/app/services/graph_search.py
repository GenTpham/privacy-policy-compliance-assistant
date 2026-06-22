import json
from openai import AsyncOpenAI
from backend.app.core.config import get_settings
from backend.app.db.neo4j_client import Neo4jClient

QUERY_EXTRACTION_PROMPT = """
Extract key entities from the user's question to query a knowledge graph.
Output ONLY a JSON array of string entity names.
Question: {question}
"""

async def extract_entities_from_query(question: str) -> list[str]:
    settings = get_settings()
    client = AsyncOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=settings.openrouter_api_key or "dummy"
    )
    
    prompt = QUERY_EXTRACTION_PROMPT.format(question=question)
    response = await client.chat.completions.create(
        model="google/gemma-4-26b-a4b",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0.0
    )
    
    content = response.choices[0].message.content
    try:
        # Assuming format: {"entities": ["A", "B"]}
        data = json.loads(content)
        if isinstance(data, list):
            return data
        elif isinstance(data, dict):
            return data.get("entities", [])
        return []
    except json.JSONDecodeError:
        return []

def retrieve_graph_context(entities: list[str], limit: int = 5) -> list[str]:
    if not entities:
        return []
        
    neo4j_client = Neo4jClient()
    # Simple 1-hop traversal from identified entities
    query = """
    UNWIND $entities AS entity_name
    MATCH (e:Entity {name: entity_name})
    MATCH (c:Chunk)-[:MENTIONS]->(e)
    RETURN DISTINCT c.text AS chunk_text, c.passage_id AS passage_id, c.id AS chunk_id
    LIMIT $limit
    """
    try:
        records = neo4j_client.execute_query(query, {"entities": entities, "limit": limit})
        return [record["chunk_text"] for record in records]
    except Exception as e:
        print(f"Neo4j retrieval error: {e}")
        return []
