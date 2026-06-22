import json
import pytest
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
