import asyncio
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import PayloadSchemaType

async def fix_index():
    client = AsyncQdrantClient(host="localhost", port=6333)
    try:
        await client.create_payload_index(
            collection_name="policies",
            field_name="user_id",
            field_schema=PayloadSchemaType.KEYWORD,
        )
        print("Created index for user_id successfully!")
    except Exception as e:
        print(f"Error: {e}")

asyncio.run(fix_index())
