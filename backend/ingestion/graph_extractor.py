import json
from openai import AsyncOpenAI
from backend.app.core.config import get_settings

EXTRACTION_PROMPT = """
You are an expert at extracting Knowledge Graphs from privacy policies.
Given the text chunk, extract entities and their relationships.
Output ONLY a valid JSON object with this schema:
{{
  "entities": [{{"name": "entity_name", "type": "Entity_Type", "description": "Short description"}}],
  "relationships": [{{"source": "entity_name", "target": "target_name", "type": "RELATION_TYPE", "description": "Reason for relation"}}]
}}
Text:
{text}
"""

import asyncio

# Limit concurrent openrouter calls to avoid crashing the connection pool or hitting rate limits
GRAPH_SEMAPHORE = asyncio.Semaphore(5)

async def extract_graph_from_chunk(text: str, retries: int = 3) -> dict:
    async with GRAPH_SEMAPHORE:
        settings = get_settings()
        if settings.llm_backend.lower() == "openai" and settings.openai_api_key:
            client = AsyncOpenAI(api_key=settings.openai_api_key)
            model_name = "gpt-4o-mini"
        else:
            client = AsyncOpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=settings.openrouter_api_key,
                default_headers={
                    "HTTP-Referer": "https://github.com/privacy-policy-compliance-assistant",
                    "X-Title": "Privacy Policy Compliance Assistant",
                },
            )
            model_name = "openai/gpt-oss-120b:free"
        
        prompt = EXTRACTION_PROMPT.format(text=text)
        
        for attempt in range(retries):
            try:
                response = await asyncio.wait_for(
                    client.chat.completions.create(
                        model=model_name,
                        messages=[{"role": "user", "content": prompt}],
                        response_format={"type": "json_object"},
                        temperature=0.1,
                        max_tokens=4096
                    ),
                    timeout=60
                )
                content = response.choices[0].message.content.strip()
                
                # Use regex to find the first JSON object in the output
                import re
                match = re.search(r'\{.*\}', content, re.DOTALL)
                if match:
                    content = match.group(0)
                    
                return json.loads(content)
            except Exception as e:
                if attempt < retries - 1:
                    wait_time = 2 ** attempt
                    print(f"[graph_extractor] Attempt {attempt+1} failed: {e}. Retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                else:
                    print(f"[graph_extractor] Error extracting graph after {retries} retries: {e}")
                    return {"entities": [], "relationships": []}
                    
        return {"entities": [], "relationships": []}
