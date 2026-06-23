from neo4j import GraphDatabase
from backend.app.core.config import get_settings

class Neo4jClient:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Neo4jClient, cls).__new__(cls)
            settings = get_settings()
            # Handle potential dummy settings in test
            try:
                cls._instance.driver = GraphDatabase.driver(
                    settings.neo4j_uri, 
                    auth=(settings.neo4j_username, settings.neo4j_password)
                )
            except Exception as e:
                # In testing environment without neo4j, this might fail depending on URI
                cls._instance.driver = None
                print(f"Warning: Failed to initialize Neo4j driver: {e}")
        return cls._instance

    def execute_query(self, query: str, parameters: dict = None) -> list[dict]:
        parameters = parameters or {}
        if not self.driver:
            raise RuntimeError("Neo4j driver is not initialized")
        with self.driver.session() as session:
            result = session.run(query, parameters)
            return [record.data() for record in result]
            
    def close(self):
        if self.driver:
            self.driver.close()
