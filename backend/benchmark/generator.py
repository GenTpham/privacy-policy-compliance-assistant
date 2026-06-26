"""
Generate answers using the project's configured OSS LLM.
Non-streaming version for batch benchmark evaluation.
"""
from openai import AsyncOpenAI


def _build_benchmark_prompt(question: str, contexts: list[str]) -> list[dict]:
    """
    Build a simple RAG prompt for benchmarking.
    Uses numbered context passages, similar to the production prompt in rag.py.
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


async def generate_answer(
    question: str,
    contexts: list[str],
    llm_client: AsyncOpenAI,
    chat_model: str,
    temperature: float = 0.0,
    max_tokens: int = 512,
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

    Returns:
        The generated answer as a string.
    """
    messages = _build_benchmark_prompt(question, contexts)

    response = await llm_client.chat.completions.create(
        model=chat_model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        stream=False,
    )

    return response.choices[0].message.content.strip()
