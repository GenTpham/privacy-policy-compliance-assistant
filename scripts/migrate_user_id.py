import asyncio
import os
from dotenv import load_dotenv
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import PointStruct

load_dotenv()

async def main():
    qdrant = AsyncQdrantClient(
        url=os.getenv("QDRANT_URL"),
        api_key=os.getenv("QDRANT_API_KEY"),
        timeout=30,
    )
    
    # Scroll and update all points
    offset = None
    total_updated = 0
    while True:
        points, offset = await qdrant.scroll(
            collection_name="policies",
            limit=100,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )
        for point in points:
            if "user_id" in point.payload:
                user_id = point.payload["user_id"]
                if not isinstance(user_id, str):
                    point.payload["user_id"] = str(user_id)
                    await qdrant.set_payload(
                        collection_name="policies",
                        payload={"user_id": str(user_id)},
                        points=[point.id]
                    )
                    total_updated += 1

        if offset is None:
            break
            
    print(f"Updated {total_updated} points to string user_id.")

asyncio.run(main())
