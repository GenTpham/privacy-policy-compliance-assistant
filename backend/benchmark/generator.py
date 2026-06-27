"""
Generate answers using the project's configured OSS LLM.
Non-streaming version for batch benchmark evaluation.
"""
import re
from openai import AsyncOpenAI

def _extract_answer_tag(content: str) -> str:
    """Extracts content inside <answer>...</answer> tags. Returns original if not found."""
    match = re.search(r"<answer>(.*?)</answer>", content, flags=re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return content.strip()

def _build_naive_prompt(question: str, contexts: list[str]) -> list[dict]:
    """
    Build a simple naive RAG prompt for benchmarking.
    """
    context_lines = [
        f"[{i}] {text}" for i, text in enumerate(contexts, start=1)
    ]
    system_content = (
        "You are a helpful assistant. "
        "Answer the question using ONLY the provided context passages below. "
        "If the passages do not contain the answer, say 'I cannot answer based on the provided context.'\n\n"
        "Context passages:\n" + "\n\n".join(context_lines)
    )
    return [
        {"role": "system", "content": system_content},
        {"role": "user", "content": question},
    ]

def _build_optimized_prompt(question: str, contexts: list[str]) -> list[dict]:
    """
    Build an optimized Quote-and-Reason RAG prompt for benchmarking.
    """
    context_lines = [
        f"[{i}] {text}" for i, text in enumerate(contexts, start=1)
    ]
    system_content = (
        "You are a helpful assistant. "
        "Answer the question using ONLY the provided context passages below. "
        "If the passages do not contain the answer, say 'I cannot answer based on the provided context.'\n\n"
        "You MUST format your output exactly like this:\n"
        "<quotes>\n- [N] \"Exact quote from context N\"\n</quotes>\n"
        "<answer>\nYour final answer citing [N]\n</answer>\n\n"
        "Context passages:\n" + "\n\n".join(context_lines)
    )
    return [
        {"role": "system", "content": system_content},
        {"role": "user", "content": question},
    ]


async def generate_answer(
    question: str,
    contexts: list[str],
    llm_client: AsyncOpenAI,
    chat_model: str,
    temperature: float = 0.0,
    max_tokens: int = 1024,
    is_optimized: bool = False,
) -> str:
    """
    Generate an answer using the LLM given a question and retrieved contexts.

    Args:
        question: The user question.
        contexts: List of retrieved chunk texts.
        llm_client: AsyncOpenAI client (configured for OpenRouter or OpenAI).
        chat_model: Model identifier string.
        temperature: Sampling temperature (0.0 for deterministic).
        max_tokens: Max tokens in the response.
        is_optimized: Whether to use the advanced Quote-and-Reason prompt.

    Returns:
        The generated answer as a string.
    """
    if is_optimized:
        messages = _build_optimized_prompt(question, contexts)
    else:
        messages = _build_naive_prompt(question, contexts)

    response = await llm_client.chat.completions.create(
        model=chat_model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        stream=False,
    )

    raw_content = response.choices[0].message.content.strip()
    
    if is_optimized:
        return _extract_answer_tag(raw_content)
    return raw_content
