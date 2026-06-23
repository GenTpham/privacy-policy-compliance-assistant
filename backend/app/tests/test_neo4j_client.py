import pytest
from unittest.mock import patch, MagicMock
from backend.app.db.neo4j_client import Neo4jClient

@patch('backend.app.db.neo4j_client.get_settings')
@patch('neo4j.GraphDatabase.driver')
def test_neo4j_client_singleton(mock_driver, mock_get_settings):
    # Mock settings
    mock_settings = MagicMock()
    mock_settings.neo4j_uri = "bolt://localhost:7687"
    mock_settings.neo4j_username = "neo4j"
    mock_settings.neo4j_password = "password"
    mock_get_settings.return_value = mock_settings

    # Mock the driver setup
    mock_driver_instance = MagicMock()
    mock_driver.return_value = mock_driver_instance
    
    client1 = Neo4jClient()
    client2 = Neo4jClient()
    
    assert client1 is client2
    # Ensure driver is initialized only once for the singleton
    assert mock_driver.call_count == 1
    
    # Test execute_query
    mock_session = mock_driver_instance.session.return_value.__enter__.return_value
    mock_result = MagicMock()
    
    # Provide a mock record with a data() method
    mock_record = MagicMock()
    mock_record.data.return_value = {"key": "value"}
    mock_session.run.return_value = [mock_record]
    
    res = client1.execute_query("RETURN 1", {"param": "val"})
    mock_session.run.assert_called_with("RETURN 1", {"param": "val"})
    assert res == [{"key": "value"}]
