import asyncio
import os
from dotenv import load_dotenv
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import PayloadSchemaType

load_dotenv()

async def fix():
    url = os.getenv('QDRANT_URL')
    api_key = os.getenv('QDRANT_API_KEY')
    qdrant = AsyncQdrantClient(url=url, api_key=api_key, timeout=30)
    
    try:
        await qdrant.create_payload_index('policies', 'user_id', PayloadSchemaType.KEYWORD)
        print("Created index for user_id")
    except Exception as e:
        print("user_id index:", e)
        
    try:
        await qdrant.create_payload_index('policies', 'title', PayloadSchemaType.KEYWORD)
        print("Created index for title")
    except Exception as e:
        print("title index:", e)
        
    print('Done!')

asyncio.run(fix())
