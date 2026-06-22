import pytest
from pydantic_core import ValidationError

from backend.app.core.config import Settings

def test_neo4j_config_attributes():
    # Attempt to initialize Settings with dummy values
    settings = Settings(
        openrouter_api_key="dummy",
        jwt_secret="dummy_32_characters_long_secret_key!",
        qdrant_url="http://dummy",
        qdrant_api_key="dummy",
        neo4j_uri="bolt://localhost:7687",
        neo4j_username="neo4j",
        neo4j_password="password"
    )
    assert settings.neo4j_uri == "bolt://localhost:7687"
    assert settings.neo4j_username == "neo4j"
    assert settings.neo4j_password == "password"
