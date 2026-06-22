import json
import os
from openai import OpenAI
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ.get("OPENROUTER_API_KEY", "dummy")
)

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

def extract_graph_from_chunk(text: str) -> dict:
    prompt = EXTRACTION_PROMPT.format(text=text)
    
    response = client.chat.completions.create(
        model="google/gemma-4-26b-a4b",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0.1
    )
    
    content = response.choices[0].message.content
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {"entities": [], "relationships": []}
