import asyncio
import os
import httpx
from backend.app.core.config import get_settings

async def test():
    settings = get_settings()
    api_key = settings.openrouter_api_key
    url = "https://openrouter.ai/api/v1/embeddings"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "nvidia/llama-nemotron-embed-vl-1b-v2:free",
        "input": [
            {
                "content": [
                    {"type": "text", "text": "What is in this image?"}
                ]
            }
        ],
        "encoding_format": "float"
    }
    
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, headers=headers, json=payload)
        print("Status:", resp.status_code)
        print("Response:", resp.text[:500])

asyncio.run(test())
