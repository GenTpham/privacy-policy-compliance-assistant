# Phase 2: Core RAG Pipeline — Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-24
**Phase:** 02-core-rag-pipeline
**Areas discussed:** SSE event format, Prompt architecture, Citation verification behavior, Conversation state ownership

---

## SSE Event Format

| Option | Description | Selected |
|--------|-------------|----------|
| Token-by-token deltas | Each SSE event carries one token: `data: {"delta": "token"}`. Final event carries citations. Matches OpenAI streaming pattern. | ✓ |
| Chunked sentences | Buffer tokens until sentence boundary, then emit. Lower event count but higher latency. | |
| Single final event | Wait for full response, emit one event. Violates RAG-05. | |

**User's choice:** Token-by-token deltas

---

| Option | Description | Selected |
|--------|-------------|----------|
| Two event types with `type` field | `data: {"type": "delta", "content": "..."}` and `data: {"type": "done", "answer": "...", "citations": [...]}` | ✓ |
| Separate SSE `event:` names | Use `event: delta` / `event: done` fields. More idiomatic SSE. | |
| OpenAI-compatible format | Mirror OpenAI exactly with `choices[].delta.content` nesting. | |

**User's choice:** Two event types with explicit `type` field

---

| Option | Description | Selected |
|--------|-------------|----------|
| POST /chat with JSON body | Standard REST chat API. `{"message": str, "history": [...]}` | ✓ |
| POST /chat/stream separately | Separate streaming vs non-streaming endpoints. | |
| GET with query params | Not viable for multi-turn history. | |

**User's choice:** POST /chat with JSON body

---

## Prompt Architecture

| Option | Description | Selected |
|--------|-------------|----------|
| Numbered list in system prompt | `[1] source: Title\ntext...` injected into system message. User message is the question only. | ✓ |
| XML-tagged blocks | `<passage id="1">` format. More token overhead. | |
| Injected into user message | Chunks appended to user turn. Mixes roles. | |

**User's choice:** Numbered list in system prompt

---

| Option | Description | Selected |
|--------|-------------|----------|
| Hard abstain | "If the provided passages do not contain the answer, respond: 'The provided policies do not contain sufficient information...'" | ✓ |
| Soft abstain with caveat | Allows partial answers with disclaimer. Risks hallucination. | |
| You decide | Delegate wording to executor. | |

**User's choice:** Hard abstain (exact wording locked)

---

| Option | Description | Selected |
|--------|-------------|----------|
| Sequential 1-based index | `[1]`–`[5]` assigned at retrieval time. Map position → Qdrant UUID in citations. | ✓ |
| Use Qdrant UUID in prompt | Full UUID in chunk header. Harder to fabricate but ugly in answer text. | |
| Hash-based short IDs | First 8 chars of UUID. Middle ground. | |

**User's choice:** Sequential 1-based index at retrieval time

---

## Citation Verification Behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Strip fabricated IDs, keep answer | Remove bad `[N]` from citations list, log warning, deliver partial answer | ✓ |
| Reject response, retry once | Re-call LLM with corrective instruction. Adds latency + cost. | |
| Return error to client | HTTP 422 on fabrication. Too strict for v1. | |

**User's choice:** Strip fabricated IDs, keep answer

---

| Option | Description | Selected |
|--------|-------------|----------|
| After streaming, on final text | Stream tokens first (meets RAG-05), verify accumulated text, emit `done` with cleaned citations | ✓ |
| Buffer full response, verify, then stream | Consistent text + citations but violates 3s first-token requirement | |

**User's choice:** After streaming, on final accumulated answer text

---

## Conversation State Ownership

| Option | Description | Selected |
|--------|-------------|----------|
| Client sends history each request | Stateless server. `POST /chat` body includes `history: [...]`. Scales horizontally. | ✓ |
| Server stores session in memory | Session dict, requires sticky sessions. Fragile across restarts. | |
| Server stores session in SQLite | Full persistence. Out of scope (v2 UX-03). | |

**User's choice:** Client-owned, stateless server

---

| Option | Description | Selected |
|--------|-------------|----------|
| Array of {role, content} | `[{"role": "user"\|"assistant", "content": "..."}]` — direct OpenAI messages pass-through | ✓ |
| Array of {question, answer} pairs | Requires server-side transformation. Extra step for no benefit. | |
| You decide | Delegate shape to planner. | |

**User's choice:** `[{"role": "user"|"assistant", "content": str}]`

---

## Claude's Discretion

- Exact Pydantic model field names and validation rules
- Gemma temperature and max_tokens defaults
- Error handling for OpenRouter timeouts and 5xx
- Regex/parser used to extract [N] citation references from answer text

## Deferred Ideas

None — discussion stayed within Phase 2 scope.
