import re
from backend.app.db.neo4j_client import Neo4jClient

def upsert_graph_to_neo4j(
    chunk_id: str,
    chunk_text: str,
    passage_id: str,
    graph: dict,
    neo4j_client: Neo4jClient,
    user_id: str = "system",
):
    # 1. Create Chunk node with user_id
    neo4j_client.execute_query(
        "MERGE (c:Chunk {id: $chunk_id, user_id: $user_id}) "
        "SET c.text = $text, c.passage_id = $passage_id",
        {"chunk_id": chunk_id, "text": chunk_text, "passage_id": passage_id, "user_id": user_id}
    )
    
    # 2. Create Entities with user_id and link to Chunk
    for entity in graph.get("entities", []):
        if not entity.get("name"):
            continue
        neo4j_client.execute_query(
            "MATCH (c:Chunk {id: $chunk_id, user_id: $user_id}) "
            "MERGE (e:Entity {name: $name, user_id: $user_id}) "
            "ON CREATE SET e.type = $type, e.description = $desc "
            "MERGE (c)-[:MENTIONS]->(e)",
            {
                "chunk_id": chunk_id,
                "name": entity.get("name"),
                "type": entity.get("type", "Unknown"),
                "desc": entity.get("description", ""),
                "user_id": user_id,
            }
        )
        
    # 3. Create Relationships between Entities (scoped by user_id)
    for rel_data in graph.get("relationships", []):
        source = rel_data.get("source")
        target = rel_data.get("target")
        raw_type = rel_data.get("type", "RELATED_TO").upper()
        rel_type = re.sub(r'[^A-Z0-9_]', '_', raw_type)
        
        if not source or not target:
            continue
            
        neo4j_client.execute_query(
            "MERGE (s:Entity {name: $source, user_id: $user_id}) "
            "MERGE (t:Entity {name: $target, user_id: $user_id}) "
            f"MERGE (s)-[r:{rel_type}]->(t) "
            "SET r.description = $desc, r.user_id = $user_id",
            {
                "source": source,
                "target": target,
                "desc": rel_data.get("description", ""),
                "user_id": user_id,
            }
        )
