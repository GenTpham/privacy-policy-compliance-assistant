<!-- GSD:project-start source:PROJECT.md -->
## Project

**Privacy Policy Compliance Assistant**

A RAG-based chatbot that lets users ask natural-language questions about privacy policies — e.g. "chính sách nào áp dụng cho lưu trữ dữ liệu khách hàng" or "quy định nào mâu thuẫn giữa hai tài liệu" — and receive answers with inline citations from the source documents. The system indexes a corpus of 17K+ privacy policy passages, retrieves the most relevant chunks via semantic search, then uses an LLM to synthesize a grounded answer. Deployed via Docker Compose with a web UI and authentication.

**Core Value:** Users can ask any compliance question and immediately get an answer with exact quotes from the authoritative policy documents — no guessing, no hallucination, traceable to source.

### Constraints

- **Tech Stack**: Python 3.11 only — explicit runtime requirement
- **Models**: OpenRouter exclusively (Gemma 4 26B A4B + Nemotron Embed VL 1B V2) — no substitutions
- **Vector Store**: Qdrant — selected for Docker Compose integration
- **Deployment**: Docker Compose — all services must run via `docker compose up`
- **Auth**: Required — UI must be gated behind login
- **No cloud cost beyond OpenRouter**: Qdrant runs locally in Docker
<!-- GSD:project-end -->

<!-- GSD:stack-start source:research/STACK.md -->
## Technology Stack

## Recommended Stack
| Component | Library | Version | Rationale |
|-----------|---------|---------|-----------|
| LLM / Embedding API | `openai` SDK | 2.32.0 | OpenRouter is OpenAI-compatible; one SDK covers both chat and embeddings via `base_url` override |
| RAG orchestration | Raw implementation | — | Eliminates framework overhead for a single-collection, single-model pipeline; LangChain is justified only when chains grow complex |
| Vector store client | `qdrant-client` | 1.17.1 | Official async-capable Python client; REST + gRPC; integrates with Docker Compose |
| API backend | `fastapi` | 0.136.0 | Async-native, auto docs, best-in-class DX for Python APIs; confirmed standard choice |
| ASGI server | `uvicorn[standard]` | latest | Production-tested ASGI server for FastAPI |
| Auth (JWT tokens) | `PyJWT` | 2.x | Actively maintained; encodes/decodes JWTs; pairs with FastAPI's `OAuth2PasswordBearer` |
| Password hashing | `pwdlib[argon2]` | latest | FastAPI docs now recommend pwdlib + Argon2 over deprecated passlib/bcrypt |
| Config management | `pydantic-settings` | 2.x | Reads `.env` via `BaseSettings`; type-safe; official FastAPI recommendation |
| Frontend | React (Vite) + Tailwind | latest | Full auth control, production-grade, Docker-friendly; Streamlit/Gradio are prototyping tools |
| DB for user accounts | SQLite (dev) / PostgreSQL (prod) | — | User auth requires persistent user store; Qdrant is not a relational store |
| ORM | `sqlalchemy[asyncio]` + `aiosqlite` | 2.x | Async SQLAlchemy 2.0 + aiosqlite for SQLite dev; swap driver for Postgres in prod |
## RAG Framework
### Recommendation: Raw implementation (no LangChain or LlamaIndex)
## OpenRouter API Compatibility
- Base URL: `https://openrouter.ai/api/v1`
- Use the `openai` Python SDK with `base_url` override — no separate client needed
- Chat completions: `client.chat.completions.create(model="google/gemma-4-26b-a4b", ...)`
- Embeddings: `client.embeddings.create(model="nvidia/llama-nemotron-embed-vl-1b-v2", input=...)`
- Context length: 131,072 tokens (generous)
- Multimodal: supports text + image input via content array format
- Available as free tier on OpenRouter (`nvidia/llama-nemotron-embed-vl-1b-v2:free`)
- Embedding dimension: not publicly documented — must be discovered at runtime or from first call. Plan to call the API with a test string during collection initialization and read `len(resp.data[0].embedding)` to set Qdrant vector size dynamically.
## Backend API
### Recommendation: FastAPI 0.136.0
- Native async support (essential for concurrent LLM API calls + Qdrant queries)
- Auto-generates OpenAPI docs useful for frontend development
- Python 3.11 compatible (requires >=3.10; 3.11 is within range)
- Industry standard for Python AI/ML API backends in 2025-2026
## Frontend
### Recommendation: React (Vite) + Tailwind CSS
- Full control over chat UI layout, citation panels, and message threading
- Standard JWT token storage + refresh flow in browser
- Easy to containerize as a static build served by nginx in Docker Compose
- Component libraries (shadcn/ui, Radix) provide accessible chat primitives without bespoke CSS
## Auth
### Recommendation: FastAPI + PyJWT + pwdlib[argon2]
- `PyJWT` — actively maintained, encodes/decodes JWTs, sign with `HS256` and a strong secret
- `pwdlib[argon2]` — FastAPI docs now recommend this over `passlib`. Passlib is effectively unmaintained; `crypt` module it relies on was removed in Python 3.13. `pwdlib` + Argon2 is the current FastAPI-endorsed replacement.
- Do NOT use `python-jose` — last release was 3+ years ago; produces DeprecationWarning on Python 3.12+
## Qdrant Setup
### Docker Compose service
### Python client initialization
# Collection creation (run once at startup / ingestion)
- Use `AsyncQdrantClient` throughout — this project is async-first
- `qdrant-client` 1.17.1 supports Python 3.10-3.14; 3.11 is fully supported
- gRPC (port 6334) is optional; REST is sufficient for this workload
## Key Library Details
### Installation
# Runtime
# Dev
### Configuration pattern (pydantic-settings)
## Recommended Project Structure
## What NOT to Use
| Library / Approach | Reason |
|-------------------|--------|
| **LangChain** | 30-40% more boilerplate, 2x framework overhead, unnecessary abstractions for a linear 3-step pipeline |
| **LlamaIndex** | Better fit than LangChain for RAG, but still overhead when the pipeline is this narrow; revisit if hybrid retrieval needed |
| **Streamlit / Gradio** | No production auth, not Docker Compose friendly as a separate service, poor citation panel customization |
| **Chainlit** | Original maintainers stepped back May 2025; community-maintained; dependency risk for production |
| **passlib + bcrypt** | passlib unmaintained; relies on `crypt` module removed in Python 3.13; replace with `pwdlib[argon2]` |
| **python-jose** | Last release 3+ years ago; DeprecationWarning on Python 3.12+; use PyJWT instead |
| **ChromaDB** | In-memory-first, less production-ready; Qdrant already chosen and is strictly better for Docker Compose |
| **FastAPI-Users** | Useful for multi-tenant apps with OAuth; overkill for a single-role gated UI |
| **Next.js** | SSR overhead is not needed for a SPA chat app; Vite + React is simpler, faster to build, equally Docker-deployable |
| **Synchronous Qdrant client** | Blocks the asyncio event loop; always use `AsyncQdrantClient` in FastAPI |
## Confidence Levels
| Area | Confidence | Basis |
|------|------------|-------|
| OpenRouter = OpenAI-compatible | HIGH | Official OpenRouter docs + quickstart confirmed `base_url` override pattern |
| FastAPI as API backend | HIGH | Official FastAPI docs; confirmed version 0.136.0 on PyPI |
| qdrant-client 1.17.1 | HIGH | Confirmed on PyPI |
| openai SDK 2.32.0 for OpenRouter | HIGH | Confirmed on PyPI; OpenRouter quickstart shows exact pattern |
| Raw RAG (no framework) | HIGH | Benchmark data + codebase complexity analysis; fits single-collection linear pipeline |
| React (Vite) over Streamlit | HIGH | Streamlit auth limitations confirmed in community sources; React is standard |
| pwdlib + Argon2 over passlib | HIGH | FastAPI docs PR #13917 migrated to pwdlib; passlib maintenance status confirmed |
| PyJWT over python-jose | HIGH | python-jose last release confirmed 3+ years ago; PyJWT actively maintained |
| Nemotron embedding dimension | LOW | OpenRouter/NVIDIA docs do not publish the output dimension; must probe at runtime |
| Chainlit maintenance risk | MEDIUM | Community sources confirm team stepped back May 2025; not verified against GitHub |
## Sources
- [OpenRouter Embeddings API Reference](https://openrouter.ai/docs/api/reference/embeddings)
- [OpenRouter Quickstart (Python OpenAI SDK)](https://openrouter.ai/docs/quickstart)
- [NVIDIA Llama Nemotron Embed VL 1B V2 on OpenRouter](https://openrouter.ai/nvidia/llama-nemotron-embed-vl-1b-v2:free)
- [FastAPI on PyPI](https://pypi.org/project/fastapi/)
- [FastAPI OAuth2 + JWT Tutorial](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/)
- [FastAPI PR #13917 — migrate to pwdlib](https://github.com/fastapi/fastapi/pull/13917)
- [passlib maintenance discussion — fastapi/fastapi #11773](https://github.com/fastapi/fastapi/discussions/11773)
- [qdrant-client on PyPI](https://pypi.org/project/qdrant-client/)
- [Qdrant Local Quickstart](https://qdrant.tech/documentation/quickstart/)
- [openai Python SDK on PyPI](https://pypi.org/project/openai/)
- [LangChain-Qdrant integration package](https://pypi.org/project/langchain-qdrant/)
- [LangChain vs LlamaIndex 2025 comparison — Latenode](https://latenode.com/blog/platform-comparisons-alternatives/automation-platform-comparisons/langchain-vs-llamaindex-2025-complete-rag-framework-comparison)
- [Best RAG Frameworks 2025 — LangCopilot](https://langcopilot.com/posts/2025-09-18-top-rag-frameworks-2024-complete-guide)
- [pydantic-settings documentation](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
- [FastAPI Settings and Environment Variables](https://fastapi.tiangolo.com/advanced/settings/)
- [Chainlit on PyPI](https://pypi.org/project/chainlit/)
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

Conventions not yet established. Will populate as patterns emerge during development.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

Architecture not yet mapped. Follow existing patterns found in the codebase.
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->
## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, or `.github/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->



<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
