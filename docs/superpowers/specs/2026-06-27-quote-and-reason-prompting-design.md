# Quote-and-Reason Prompting Design

## Objective
Improve the Faithfulness metric of the Optimized RAG pipeline from ~0.80 to >0.90 by forcing the LLM to ground its answers using a "Quote-and-Reason" (Chain-of-Thought) technique.

## Context
Currently, the system uses a standard prompt that tells the LLM to answer based ONLY on the provided context. However, LLMs can still hallucinate or inject parametric knowledge. By forcing the LLM to first extract verbatim quotes before answering, we significantly restrict its ability to hallucinate.

## Architecture & Prompt Changes

### 1. XML Tag Structure
Both the benchmarking pipeline and the production RAG service will adopt a unified prompt structure requiring the LLM to output its response using strict XML tags:

```xml
<quotes>
- [1] "Exact quote from context 1..."
- [3] "Exact quote from context 3..."
</quotes>
<answer>
The final answer synthesizing the quotes, citing [1] and [3].
</answer>
```

### 2. Pipeline Integration

**A. `backend/benchmark/generator.py`**
- Update `_build_benchmark_prompt` to include the XML tag requirement.
- Modify the `generate_answer` function to parse the LLM's response. It must extract only the content within the `<answer>` tags using Regex before returning it. If the `<answer>` tag is missing (fallback scenario), return the full text. This ensures Ragas evaluates only the final answer without being confused by the intermediate quotes.

**B. `backend/app/services/rag.py` (Production)**
- Update `_build_messages` and `_build_conflict_messages` to include the XML tag requirement in the `system_content`.
- The streaming pipeline (`stream_answer` and `stream_conflict_answer`) will remain largely unchanged. The XML tags (`<quotes>` and `<answer>`) will stream down to the client as-is. This serves as a transparent "AI Thinking" indicator for the user, aligning with modern chatbot UX patterns.

## Testing & Validation
- **Unit Tests**: Ensure the Regex parser in `generator.py` correctly extracts the answer and handles edge cases (e.g., missing tags).
- **Benchmark Run**: Execute `python -m backend.benchmark.run_benchmark --num-queries 100` to validate that the Faithfulness score rises above 0.90 across a statistically significant sample.

## Scope & Ambiguity Check
- The scope is contained purely within the prompt strings and a lightweight parser in the benchmark module.
- There are no database schema changes, frontend changes, or dependency upgrades required.
- **Handling missing tags**: If the LLM disobeys the instruction and outputs raw text without `<answer>` tags, the system will gracefully fallback to treating the entire response as the answer.
