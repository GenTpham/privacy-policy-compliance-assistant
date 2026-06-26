"""Tests for benchmark answer generator."""
from unittest.mock import AsyncMock, MagicMock
from types import SimpleNamespace

import pytest

from backend.benchmark.generator import generate_answer


@pytest.fixture
def mock_llm_client():
    client = AsyncMock()
    choice = SimpleNamespace(
        message=SimpleNamespace(content="The answer is 42.")
    )
    client.chat.completions.create.return_value = SimpleNamespace(choices=[choice])
    return client


class TestGenerateAnswer:
    @pytest.mark.asyncio
    async def test_returns_answer_string(self, mock_llm_client):
        result = await generate_answer(
            question="What is the meaning?",
            contexts=["Context passage 1", "Context passage 2"],
            llm_client=mock_llm_client,
            chat_model="test-model",
        )
        assert isinstance(result, str)
        assert result == "The answer is 42."

    @pytest.mark.asyncio
    async def test_sends_contexts_in_prompt(self, mock_llm_client):
        await generate_answer(
            question="What?",
            contexts=["Alpha context", "Beta context"],
            llm_client=mock_llm_client,
            chat_model="test-model",
        )
        call_args = mock_llm_client.chat.completions.create.call_args
        messages = call_args.kwargs["messages"]
        system_msg = messages[0]["content"]
        assert "Alpha context" in system_msg
        assert "Beta context" in system_msg

    @pytest.mark.asyncio
    async def test_empty_contexts_still_works(self, mock_llm_client):
        result = await generate_answer(
            question="No context?",
            contexts=[],
            llm_client=mock_llm_client,
            chat_model="test-model",
        )
        assert isinstance(result, str)
