import asyncio
import os
import sqlite3
from dotenv import load_dotenv
from qdrant_client import AsyncQdrantClient
from neo4j import GraphDatabase

load_dotenv()

async def reset_qdrant():
    try:
        qdrant = AsyncQdrantClient(
            url=os.getenv("QDRANT_URL", "http://localhost:6333"),
            api_key=os.getenv("QDRANT_API_KEY"),
            timeout=30,
        )
        await qdrant.delete_collection("policies")
        print("Deleted 'policies' collection in Qdrant.")
    except Exception as e:
        print(f"Failed to delete Qdrant collection: {e}")

def reset_neo4j():
    try:
        URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        USER = os.getenv("NEO4J_USER", "neo4j")
        PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
        
        driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))
        with driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
        driver.close()
        print("Deleted all nodes and relationships in Neo4j.")
    except Exception as e:
        print(f"Failed to clear Neo4j: {e}")

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def reset_postgres():
    try:
        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            print("DATABASE_URL not found, skipping postgres reset.")
            return
            
        engine = create_async_engine(db_url)
        async with engine.begin() as conn:
            await conn.execute(text("DELETE FROM documents"))
        await engine.dispose()
        print("Cleared 'documents' table in Postgres.")
    except Exception as e:
        print(f"Failed to clear Postgres: {e}")

async def main():
    print("Starting full database reset...")
    await reset_qdrant()
    reset_neo4j()
    await reset_postgres()
    print("Done!")

if __name__ == "__main__":
    asyncio.run(main())
