import json
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from backend.ingestion.graph_extractor import extract_graph_from_chunk

@pytest.mark.asyncio
@patch('backend.ingestion.graph_extractor.AsyncOpenAI')
async def test_extract_graph_from_chunk(mock_openai_class):
    # Mock LLM response
    mock_response = MagicMock()
    mock_response.choices[0].message.content = json.dumps({
        "entities": [{"name": "User", "type": "Actor", "description": "A person"}],
        "relationships": [{"source": "User", "target": "System", "type": "USES", "description": "Interacts with"}]
    })
    
    mock_client_instance = AsyncMock()
    mock_client_instance.chat.completions.create.return_value = mock_response
    mock_openai_class.return_value = mock_client_instance

    result = await extract_graph_from_chunk("The user uses the system.")
    
    assert "entities" in result
    assert "relationships" in result
    assert result["entities"][0]["name"] == "User"
    assert result["relationships"][0]["type"] == "USES"
