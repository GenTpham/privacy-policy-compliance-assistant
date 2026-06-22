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

async def extract_graph_from_chunk(text: str) -> dict:
    settings = get_settings()
    client = AsyncOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=settings.openrouter_api_key,
        default_headers={
            "HTTP-Referer": "https://github.com/privacy-policy-compliance-assistant",
            "X-Title": "Privacy Policy Compliance Assistant",
        },
    )
    
    prompt = EXTRACTION_PROMPT.format(text=text)
    
    try:
        response = await client.chat.completions.create(
            model="google/gemma-4-26b-a4b-it",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.1,
            max_tokens=4096
        )
        content = response.choices[0].message.content.strip()
        # Clean up markdown code blocks if the model wrapped the output
        if content.startswith("```"):
            lines = content.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            content = "\n".join(lines).strip()
            
        return json.loads(content)
    except Exception as e:
        print(f"[graph_extractor] Error extracting graph: {e}")
        return {"entities": [], "relationships": []}
