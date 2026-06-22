import os
import pytest
from backend.app.core.config import Settings
from pydantic import ValidationError

def test_neo4j_settings_exist():
    # Attempt to instantiate with dummy required vars
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
