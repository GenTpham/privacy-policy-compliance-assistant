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
    if settings.llm_backend.lower() == "openai" and settings.openai_api_key:
        client = AsyncOpenAI(api_key=settings.openai_api_key)
        model_name = "gpt-4o-mini"
    else:
        client = AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=settings.openrouter_api_key
        )
        model_name = "openai/gpt-oss-120b:free"
    
    prompt = QUERY_EXTRACTION_PROMPT.format(question=question)
    response = await client.chat.completions.create(
        model=model_name,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0.0,
        max_tokens=1024
    )
    
    content = response.choices[0].message.content.strip()
    if content.startswith("```"):
        lines = content.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        content = "\n".join(lines).strip()
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

try:
    from opentelemetry import trace as _otel_trace
    _tracer = _otel_trace.get_tracer(__name__)
except ImportError:
    _tracer = None

def retrieve_graph_context(entities: list[str], limit: int = 5, user_id: int | None = None) -> list[str]:
    if not entities:
        return []
        
    neo4j_client = Neo4jClient()
    # Simple 1-hop traversal from identified entities
    if user_id is not None:
        query = """
        UNWIND $entities AS entity_name
        MATCH (e:Entity {name: entity_name})
        WHERE e.user_id = $user_id_str OR e.user_id = 'system' OR e.user_id IS NULL
        MATCH (c:Chunk)-[:MENTIONS]->(e)
        WHERE c.user_id = $user_id_str OR c.user_id = 'system' OR c.user_id IS NULL
        RETURN DISTINCT c.text AS chunk_text, c.passage_id AS passage_id, c.id AS chunk_id
        LIMIT $limit
        """
        params = {"entities": entities, "limit": limit, "user_id_str": str(user_id)}
    else:
        query = """
        UNWIND $entities AS entity_name
        MATCH (e:Entity {name: entity_name})
        MATCH (c:Chunk)-[:MENTIONS]->(e)
        RETURN DISTINCT c.text AS chunk_text, c.passage_id AS passage_id, c.id AS chunk_id
        LIMIT $limit
        """
        params = {"entities": entities, "limit": limit}

    try:
        if _tracer:
            with _tracer.start_as_current_span(
                "neo4j.retrieve",
                attributes={
                    "neo4j.query.text": query.strip(),
                    "neo4j.query.entities": str(entities),
                    "neo4j.query.limit": limit,
                    "neo4j.query.user_id": str(user_id) if user_id is not None else "None"
                }
            ) as span:
                records = neo4j_client.execute_query(query, params)
                if span:
                    span.set_attribute("neo4j.results_count", len(records))
        else:
            records = neo4j_client.execute_query(query, params)
            
        return [record["chunk_text"] for record in records]
    except Exception as e:
        print(f"Neo4j retrieval error: {e}")
        return []
