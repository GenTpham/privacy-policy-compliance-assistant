import asyncio
import os
from dotenv import load_dotenv
from qdrant_client import AsyncQdrantClient

load_dotenv()

async def main():
    qdrant = AsyncQdrantClient(
        url=os.getenv("QDRANT_URL"),
        api_key=os.getenv("QDRANT_API_KEY"),
        timeout=30,
    )
    await qdrant.delete_payload_index("policies", "user_id")
    print("Deleted user_id index.")

asyncio.run(main())
