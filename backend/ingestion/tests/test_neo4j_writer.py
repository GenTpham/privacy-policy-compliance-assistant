import sys
sys.path.insert(0, r"D:\data\code\privacy-policy-compliance-assistant")
from unittest.mock import MagicMock
from backend.ingestion.neo4j_writer import upsert_graph_to_neo4j

def test_upsert_graph_to_neo4j_uses_system_user_id_by_default():
    mock_client = MagicMock()
    
    graph = {
        "entities": [{"name": "User", "type": "Actor", "description": "Person"}],
        "relationships": [{"source": "User", "target": "System", "type": "USES", "description": "Interacts"}]
    }
    
    upsert_graph_to_neo4j("chunk_1", "text", "passage_1", graph, mock_client)
    
    assert mock_client.execute_query.call_count == 3
    
    # 1. Chunk node creation
    chunk_call = mock_client.execute_query.call_args_list[0]
    assert "MERGE (c:Chunk {id: $chunk_id, user_id: $user_id})" in chunk_call[0][0]
    assert chunk_call[0][1]["user_id"] == "system"
    
    # 2. Entity node creation
    entity_call = mock_client.execute_query.call_args_list[1]
    assert "MATCH (c:Chunk {id: $chunk_id, user_id: $user_id})" in entity_call[0][0]
    assert "MERGE (e:Entity {name: $name, user_id: $user_id})" in entity_call[0][0]
    assert entity_call[0][1]["user_id"] == "system"

    # 3. Relationship creation
    rel_call = mock_client.execute_query.call_args_list[2]
    assert "SET r.description = $desc, r.user_id = $user_id" in rel_call[0][0]
    assert rel_call[0][1]["user_id"] == "system"

def test_upsert_graph_to_neo4j_with_custom_user_id():
    mock_client = MagicMock()
    
    graph = {
        "entities": [{"name": "User", "type": "Actor", "description": "Person"}],
        "relationships": [{"source": "User", "target": "System", "type": "USES", "description": "Interacts"}]
    }
    
    upsert_graph_to_neo4j("chunk_1", "text", "passage_1", graph, mock_client, user_id="42")
    
    assert mock_client.execute_query.call_count == 3
    
    # 1. Chunk node creation
    chunk_call = mock_client.execute_query.call_args_list[0]
    assert "MERGE (c:Chunk {id: $chunk_id, user_id: $user_id})" in chunk_call[0][0]
    assert chunk_call[0][1]["user_id"] == "42"
    
    # 2. Entity node creation
    entity_call = mock_client.execute_query.call_args_list[1]
    assert "MATCH (c:Chunk {id: $chunk_id, user_id: $user_id})" in entity_call[0][0]
    assert "MERGE (e:Entity {name: $name, user_id: $user_id})" in entity_call[0][0]
    assert entity_call[0][1]["user_id"] == "42"

    # 3. Relationship creation
    rel_call = mock_client.execute_query.call_args_list[2]
    assert "SET r.description = $desc, r.user_id = $user_id" in rel_call[0][0]
    assert rel_call[0][1]["user_id"] == "42"

if __name__ == "__main__":
    test_upsert_graph_to_neo4j_uses_system_user_id_by_default()
    test_upsert_graph_to_neo4j_with_custom_user_id()
    print("ALL TESTS PASSED")
