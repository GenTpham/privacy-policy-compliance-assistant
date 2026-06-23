from unittest.mock import MagicMock
from backend.ingestion.neo4j_writer import upsert_graph_to_neo4j

def test_upsert_graph_to_neo4j():
    mock_client = MagicMock()
    
    graph = {
        "entities": [{"name": "User", "type": "Actor", "description": "Person"}],
        "relationships": [{"source": "User", "target": "System", "type": "USES", "description": "Interacts"}]
    }
    
    upsert_graph_to_neo4j("chunk_1", "text", "passage_1", graph, mock_client)
    
    assert mock_client.execute_query.call_count == 3
