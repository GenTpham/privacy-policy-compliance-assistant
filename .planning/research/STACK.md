# Stack Research: Privacy Policy Compliance Assistant

**Project:** RAG chatbot for privacy policy Q&A with inline citations
**Researched:** 2026-04-21
**Python constraint:** 3.11 (explicit, non-negotiable)

---

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

---

## RAG Framework

### Recommendation: Raw implementation (no LangChain or LlamaIndex)

**Rationale:**

This project has a narrow, fixed RAG pipeline:
1. Embed query via OpenRouter Nemotron embedding endpoint
2. Search Qdrant collection for top-k chunks
3. Construct prompt with retrieved context + user question
4. Call OpenRouter Gemma 4 via chat completions
5. Return answer + source citations

That is ~50 lines of straightforward Python. LangChain adds 30-40% more code, additional abstractions, and 2-3x more framework overhead (~10ms vs ~6ms per call) compared to raw code, without providing anything this specific pipeline needs.

**When to reconsider:** If retrieval strategies need to branch (hybrid sparse+dense, query decomposition, multi-hop), LlamaIndex becomes a good fit. At that point reach for `llama-index-vector-stores-qdrant` and `llama-index-embeddings-openai`. Do not introduce LangChain unless you need LangGraph-style workflow orchestration.

**Key raw implementation pattern:**

```python
from openai import AsyncOpenAI
from qdrant_client import AsyncQdrantClient

openrouter = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=settings.openrouter_api_key,
)

async def embed(text: str) -> list[float]:
    resp = await openrouter.embeddings.create(
        model="nvidia/llama-nemotron-embed-vl-1b-v2",
        input=text,
    )
    return resp.data[0].embedding

async def retrieve(query_vec: list[float], top_k: int = 5):
    return await qdrant.search(
        collection_name="policies",
        query_vector=query_vec,
        limit=top_k,
        with_payload=True,
    )
```

---

## OpenRouter API Compatibility

**Confirmed HIGH confidence:** OpenRouter is fully OpenAI-compatible for both chat completions and embeddings.

- Base URL: `https://openrouter.ai/api/v1`
- Use the `openai` Python SDK with `base_url` override — no separate client needed
- Chat completions: `client.chat.completions.create(model="google/gemma-4-26b-a4b", ...)`
- Embeddings: `client.embeddings.create(model="nvidia/llama-nemotron-embed-vl-1b-v2", input=...)`

**Nemotron Embed VL 1B V2 specifics:**
- Context length: 131,072 tokens (generous)
- Multimodal: supports text + image input via content array format
- Available as free tier on OpenRouter (`nvidia/llama-nemotron-embed-vl-1b-v2:free`)
- Embedding dimension: not publicly documented — must be discovered at runtime or from first call. Plan to call the API with a test string during collection initialization and read `len(resp.data[0].embedding)` to set Qdrant vector size dynamically.

Optional attribution headers (not required, but recommended by OpenRouter):
```python
extra_headers={
    "HTTP-Referer": "https://your-app-url",
    "X-OpenRouter-Title": "Privacy Policy Assistant",
}
```

---

## Backend API

### Recommendation: FastAPI 0.136.0

FastAPI is the correct choice. Confirmed by:
- Native async support (essential for concurrent LLM API calls + Qdrant queries)
- Auto-generates OpenAPI docs useful for frontend development
- Python 3.11 compatible (requires >=3.10; 3.11 is within range)
- Industry standard for Python AI/ML API backends in 2025-2026

**ASGI stack:**
```
uvicorn[standard]  # for production; includes httptools + uvloop
```

**Streaming:** FastAPI supports `StreamingResponse` for server-sent events — use this to stream LLM tokens to the frontend rather than waiting for full completion.

---

## Frontend

### Recommendation: React (Vite) + Tailwind CSS

**Reject Streamlit and Gradio for this project** — both lack production-grade auth, have limited customization for citation display, and produce single-process apps that don't integrate cleanly with a separate FastAPI backend in Docker Compose.

**React (Vite) is the right choice because:**
- Full control over chat UI layout, citation panels, and message threading
- Standard JWT token storage + refresh flow in browser
- Easy to containerize as a static build served by nginx in Docker Compose
- Component libraries (shadcn/ui, Radix) provide accessible chat primitives without bespoke CSS

**Chainlit note:** Chainlit is a Python-native chat UI that integrates with FastAPI and has built-in auth. The original team stepped back as of May 2025; the project is now community-maintained. The maintenance risk is LOW for MVP but MEDIUM for long-term. Do not use it as the sole frontend if production longevity matters.

**Recommended React setup:**
```
Vite + React 18 + TypeScript
Tailwind CSS (utility-first, zero runtime cost)
shadcn/ui (accessible component primitives)
TanStack Query (server state / API calls)
```

---

## Auth

### Recommendation: FastAPI + PyJWT + pwdlib[argon2]

Standard pattern for a self-contained FastAPI application with username/password login:

1. User POSTs to `/auth/token` with `username` + `password`
2. FastAPI verifies password hash with `pwdlib` Argon2
3. On success: issue short-lived access token (JWT, 30 min) + refresh token (JWT, 7 days)
4. All protected endpoints use `Depends(get_current_user)` with `OAuth2PasswordBearer`
5. Frontend stores access token in memory (not localStorage); refresh token in httpOnly cookie

**Library choices:**
- `PyJWT` — actively maintained, encodes/decodes JWTs, sign with `HS256` and a strong secret
- `pwdlib[argon2]` — FastAPI docs now recommend this over `passlib`. Passlib is effectively unmaintained; `crypt` module it relies on was removed in Python 3.13. `pwdlib` + Argon2 is the current FastAPI-endorsed replacement.
- Do NOT use `python-jose` — last release was 3+ years ago; produces DeprecationWarning on Python 3.12+

**Minimal auth config:**
```python
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher
import jwt

password_hash = PasswordHash([Argon2Hasher()])

def verify_password(plain: str, hashed: str) -> bool:
    return password_hash.verify(plain, hashed)

def create_access_token(sub: str, secret: str, expire_minutes: int = 30) -> str:
    payload = {"sub": sub, "exp": datetime.utcnow() + timedelta(minutes=expire_minutes)}
    return jwt.encode(payload, secret, algorithm="HS256")
```

---

## Qdrant Setup

### Docker Compose service

```yaml
services:
  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - "127.0.0.1:6333:6333"   # REST API
      - "127.0.0.1:6334:6334"   # gRPC
    volumes:
      - qdrant_storage:/qdrant/storage
    environment:
      QDRANT__SERVICE__API_KEY: "${QDRANT_API_KEY}"

volumes:
  qdrant_storage:
```

### Python client initialization

```python
from qdrant_client import AsyncQdrantClient, models

qdrant = AsyncQdrantClient(
    host="qdrant",   # Docker Compose service name
    port=6333,
    api_key=settings.qdrant_api_key,  # optional for local dev
)

# Collection creation (run once at startup / ingestion)
await qdrant.create_collection(
    collection_name="policies",
    vectors_config=models.VectorParams(
        size=EMBEDDING_DIM,   # discovered at runtime from first embed call
        distance=models.Distance.COSINE,
    ),
)
```

- Use `AsyncQdrantClient` throughout — this project is async-first
- `qdrant-client` 1.17.1 supports Python 3.10-3.14; 3.11 is fully supported
- gRPC (port 6334) is optional; REST is sufficient for this workload

---

## Key Library Details

### Installation

```bash
# Runtime
pip install fastapi==0.136.0
pip install "uvicorn[standard]"
pip install qdrant-client==1.17.1
pip install openai==2.32.0
pip install PyJWT
pip install "pwdlib[argon2]"
pip install "pydantic-settings>=2.0"
pip install "sqlalchemy[asyncio]"
pip install aiosqlite        # dev; swap for asyncpg + postgresql in prod
pip install python-multipart  # required for FastAPI form data (login)

# Dev
pip install pytest pytest-asyncio httpx
```

### Configuration pattern (pydantic-settings)

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    openrouter_api_key: str
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_api_key: str | None = None
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    model_config = {"env_file": ".env"}

from functools import lru_cache

@lru_cache
def get_settings() -> Settings:
    return Settings()
```

---

## Recommended Project Structure

```
privacy-policy-compliance-assistant/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app factory, startup events
│   │   ├── core/
│   │   │   ├── config.py        # pydantic-settings Settings class
│   │   │   └── security.py      # JWT encode/decode, password hash
│   │   ├── api/
│   │   │   ├── auth.py          # /auth/token, /auth/refresh endpoints
│   │   │   └── chat.py          # /chat POST endpoint (SSE streaming)
│   │   ├── services/
│   │   │   ├── embedder.py      # OpenRouter embed() call
│   │   │   ├── retriever.py     # Qdrant search()
│   │   │   └── generator.py     # OpenRouter chat completions
│   │   ├── rag/
│   │   │   └── pipeline.py      # Orchestrates embed → retrieve → generate
│   │   └── db/
│   │       ├── session.py       # SQLAlchemy async engine + session
│   │       └── models.py        # User ORM model
│   ├── ingestion/
│   │   └── ingest.py            # One-shot script: load JSON → embed → upsert Qdrant
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── Chat.tsx
│   │   │   ├── MessageBubble.tsx
│   │   │   └── CitationPanel.tsx
│   │   ├── pages/
│   │   │   ├── Login.tsx
│   │   │   └── App.tsx
│   │   └── api/
│   │       └── client.ts        # fetch wrapper with JWT header injection
│   └── Dockerfile
├── dataset/
│   └── json/                    # existing corpus (read-only at runtime)
├── docker-compose.yml
├── .env.example
└── .planning/
```

---

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

---

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

---

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
