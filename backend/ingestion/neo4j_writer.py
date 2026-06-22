from backend.app.db.neo4j_client import Neo4jClient

def upsert_graph_to_neo4j(chunk_id: str, chunk_text: str, passage_id: str, graph: dict, neo4j_client: Neo4jClient):
    # 1. Create Chunk node
    neo4j_client.execute_query(
        "MERGE (c:Chunk {id: $chunk_id}) "
        "SET c.text = $text, c.passage_id = $passage_id",
        {"chunk_id": chunk_id, "text": chunk_text, "passage_id": passage_id}
    )
    
    # 2. Create Entities and link to Chunk
    for entity in graph.get("entities", []):
        if not entity.get("name"):
            continue
        neo4j_client.execute_query(
            "MATCH (c:Chunk {id: $chunk_id}) "
            "MERGE (e:Entity {name: $name}) "
            "ON CREATE SET e.type = $type, e.description = $desc "
            "MERGE (c)-[:MENTIONS]->(e)",
            {
                "chunk_id": chunk_id,
                "name": entity.get("name"),
                "type": entity.get("type", "Unknown"),
                "desc": entity.get("description", "")
            }
        )
        
    # 3. Create Relationships between Entities
    for rel in graph.get("relationships", []):
        source = rel.get("source")
        target = rel.get("target")
        import re
        raw_type = rel.get("type", "RELATED_TO").upper()
        rel_type = re.sub(r'[^A-Z0-9_]', '_', raw_type)
        
        if not source or not target:
            continue
            
        neo4j_client.execute_query(
            "MERGE (s:Entity {name: $source}) "
            "MERGE (t:Entity {name: $target}) "
            f"MERGE (s)-[r:{rel_type}]->(t) "
            "SET r.description = $desc",
            {
                "source": source,
                "target": target,
                "desc": rel.get("description", "")
            }
        )
