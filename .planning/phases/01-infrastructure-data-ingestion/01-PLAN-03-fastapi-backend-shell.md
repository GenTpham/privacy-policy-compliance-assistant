---
id: 01-PLAN-03
wave: 2
depends_on:
  - 01-PLAN-01
phase: 01-infrastructure-data-ingestion
goal: FastAPI backend shell with pydantic-settings config, lifespan collection bootstrap, and health endpoint
files_modified:
  - backend/app/core/config.py
  - backend/app/core/telemetry.py
  - backend/app/main.py
autonomous: true
requirements:
  - INFRA-03
  - INFRA-04
  - INFRA-05
---

<objective>
Implement the pydantic-settings `Settings` class (with fail-fast validation), the FastAPI app factory with a lifespan context manager that bootstraps the `policies` Qdrant collection on startup, and a `/health` endpoint. Also sets up Arize Phoenix telemetry wiring.

Purpose: Plan 04 (ingestion) imports `backend.app.core.config.get_settings()` — this plan delivers that module. The FastAPI lifespan also provides the "belt" in the belt-and-suspenders collection ownership pattern (D-08): even if ingestion was never run, the API will create the collection on startup.
Output: config.py, telemetry.py, main.py — a runnable FastAPI app that fails fast on missing secrets and bootstraps Qdrant on startup.
</objective>

<execution_context>
@D:\data\code\privacy-policy-compliance-assistant\.planning\phases\01-infrastructure-data-ingestion\01-AI-SPEC.md
</execution_context>

<context>
@D:\data\code\privacy-policy-compliance-assistant\.planning\ROADMAP.md
@D:\data\code\privacy-policy-compliance-assistant\.planning\phases\01-infrastructure-data-ingestion\01-CONTEXT.md
@D:\data\code\privacy-policy-compliance-assistant\.planning\research\STACK.md

<interfaces>
<!-- From CONTEXT.md decisions: -->
<!-- D-08: FastAPI lifespan ensures_collection on startup (belt-and-suspenders with ingest script) -->
<!-- D-09: Skip collection creation if exists — idempotent -->
<!-- D-10: COSINE distance metric (IMMUTABLE) -->
<!-- D-13: host="qdrant" inside Docker Compose; "localhost" for local dev -->
<!-- D-14: All secrets from .env via pydantic-settings; fail fast if missing -->
<!--  -->
<!-- From AI-SPEC §4b.1 — exact Settings class: -->
<!--   openrouter_api_key: str           (required — no default) -->
<!--   qdrant_host: str = "localhost"    (override to "qdrant" in Docker via env var) -->
<!--   qdrant_port: int = 6333 -->
<!--   qdrant_api_key: str | None = None -->
<!--   jwt_secret: str                   (required — no default) -->
<!--   model_config = {"env_file": ".env"} -->
<!--  -->
<!-- From AI-SPEC §4b.2 — lifespan pattern (correct): -->
<!--   @asynccontextmanager -->
<!--   async def lifespan(app: FastAPI): -->
<!--       dim = await probe_embedding_dim() -->
<!--       await ensure_collection(dim) -->
<!--       yield -->
<!--  -->
<!-- From AI-SPEC §7 — telemetry.py: -->
<!--   setup_tracing(endpoint="http://phoenix:4317") -->
<!--   OpenAIInstrumentor().instrument() -->
<!--  -->
<!-- Guardrail from AI-SPEC §6: -->
<!--   After ensure_collection(), verify distance == Distance.COSINE — raise RuntimeError if not -->
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create backend/app/core/config.py with pydantic-settings Settings</name>
  <files>backend/app/core/config.py</files>
  <read_first>
    - D:\data\code\privacy-policy-compliance-assistant\.planning\phases\01-infrastructure-data-ingestion\01-AI-SPEC.md (§4b.1 Structured Outputs — Config validation / startup fail-fast pattern)
    - D:\data\code\privacy-policy-compliance-assistant\.planning\research\STACK.md (Configuration pattern section)
    - D:\data\code\privacy-policy-compliance-assistant\.planning\phases\01-infrastructure-data-ingestion\01-CONTEXT.md (D-14)
    - D:\data\code\privacy-policy-compliance-assistant\.env.example (if it exists — to confirm exact env var names)
  </read_first>
  <action>
Create `backend/app/core/config.py` with this exact implementation:

```python
"""
backend/app/core/config.py
Pydantic-settings configuration — reads secrets from .env at startup.
Missing required fields raise ValidationError immediately (fail-fast pattern).
"""
from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Required — no default. Missing value raises ValidationError at startup.
    openrouter_api_key: str
    jwt_secret: str

    # Qdrant connection — override QDRANT_HOST to "qdrant" inside Docker Compose
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_api_key: str | None = None

    # JWT configuration (used in Phase 3+)
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    """
    Return a singleton Settings instance.
    @lru_cache ensures Settings() is called once per process.
    Raises pydantic_core.ValidationError if required env vars are absent.
    """
    return Settings()
```

The `@lru_cache` decorator ensures `Settings()` is instantiated only once — if required vars are absent from `.env`, `ValidationError` propagates to the caller with a clear field-level error message (per D-14 fail-fast requirement).
  </action>
  <verify>
    <automated>grep "class Settings(BaseSettings)" D:/data/code/privacy-policy-compliance-assistant/backend/app/core/config.py && grep "openrouter_api_key: str" D:/data/code/privacy-policy-compliance-assistant/backend/app/core/config.py && grep "jwt_secret: str" D:/data/code/privacy-policy-compliance-assistant/backend/app/core/config.py && grep "@lru_cache" D:/data/code/privacy-policy-compliance-assistant/backend/app/core/config.py && grep 'env_file.*\.env' D:/data/code/privacy-policy-compliance-assistant/backend/app/core/config.py</automated>
  </verify>
  <done>config.py has Settings(BaseSettings) with openrouter_api_key (required), jwt_secret (required), qdrant_host (default "localhost"), qdrant_port (default 6333), qdrant_api_key (optional). get_settings() wrapped with @lru_cache. model_config reads from ".env".</done>
</task>

<task type="auto">
  <name>Task 2: Create backend/app/core/telemetry.py and backend/app/main.py</name>
  <files>backend/app/core/telemetry.py, backend/app/main.py</files>
  <read_first>
    - D:\data\code\privacy-policy-compliance-assistant\.planning\phases\01-infrastructure-data-ingestion\01-AI-SPEC.md (§4b.2 lifespan pattern; §7 Production Monitoring — telemetry.py snippet)
    - D:\data\code\privacy-policy-compliance-assistant\.planning\phases\01-infrastructure-data-ingestion\01-CONTEXT.md (D-08, D-09, D-10)
    - D:\data\code\privacy-policy-compliance-assistant\backend\app\core\config.py (if created — to import get_settings)
  </read_first>
  <action>
**File 1: `backend/app/core/telemetry.py`**

Create with the Phoenix OTLP tracing setup from AI-SPEC §7. This module is imported in main.py's lifespan:

```python
"""
backend/app/core/telemetry.py
Arize Phoenix tracing — instruments the openai SDK automatically.
Call setup_tracing() once at FastAPI startup.
"""
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter


def setup_tracing(endpoint: str = "http://phoenix:4317") -> None:
    """
    Instrument the openai SDK via OpenTelemetry.
    Every embeddings.create() and chat.completions.create() call is traced automatically.
    Call once at FastAPI startup — not per-request.
    """
    try:
        from openinference.instrumentation.openai import OpenAIInstrumentor
        exporter = OTLPSpanExporter(endpoint=endpoint)
        provider = TracerProvider()
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)
        OpenAIInstrumentor().instrument()
        print(f"[telemetry] Tracing enabled — exporting to {endpoint}")
    except ImportError:
        # openinference-instrumentation-openai not installed — tracing disabled
        print("[telemetry] openinference not installed — tracing disabled")
    except Exception as exc:
        # Phoenix may not be running in local dev — log and continue
        print(f"[telemetry] Failed to enable tracing: {exc} — continuing without tracing")
```

**File 2: `backend/app/main.py`**

Create the FastAPI app factory with a lifespan that:
1. Calls `setup_tracing()` to enable Phoenix telemetry
2. Probes Nemotron embedding dimension (one API call)
3. Ensures the `policies` Qdrant collection exists with COSINE distance (D-08, D-09, D-10)
4. Verifies distance metric is COSINE after creation — raises RuntimeError if not (AI-SPEC §6 guardrail)

```python
"""
backend/app/main.py
FastAPI application factory.
Lifespan: probes embedding dimension, bootstraps Qdrant 'policies' collection.
"""
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from openai import AsyncOpenAI
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, VectorParams

from backend.app.core.config import get_settings
from backend.app.core.telemetry import setup_tracing

COLLECTION_NAME = "policies"


async def _probe_embedding_dim(client: AsyncOpenAI, model: str) -> int:
    """
    Call the embedding API once with a test string and return the vector dimension.
    Nemotron's output dimension is not documented — must be discovered at runtime.
    Never hardcode this value (AI-SPEC Critical Failure Mode 5).
    """
    resp = await client.embeddings.create(model=model, input="probe")
    dim = len(resp.data[0].embedding)
    print(f"[startup] Nemotron embedding dimension: {dim}")
    return dim


async def _ensure_collection(qdrant: AsyncQdrantClient, dim: int) -> None:
    """
    Create the 'policies' collection with COSINE distance if it does not exist.
    COSINE is IMMUTABLE after creation — verify after create (AI-SPEC §6 guardrail).
    Decision D-09: skip creation if collection already exists, proceed to verify.
    """
    existing = {c.name for c in (await qdrant.get_collections()).collections}
    if COLLECTION_NAME not in existing:
        await qdrant.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
        )
        print(f"[startup] Created collection '{COLLECTION_NAME}' (dim={dim}, COSINE).")
    else:
        print(f"[startup] Collection '{COLLECTION_NAME}' already exists — skipping creation.")

    # Guardrail: verify distance metric is COSINE regardless of whether we just created it
    info = await qdrant.get_collection(COLLECTION_NAME)
    actual_distance = info.config.params.vectors.distance
    if actual_distance != Distance.COSINE:
        raise RuntimeError(
            f"Collection '{COLLECTION_NAME}' distance metric is {actual_distance}, "
            f"expected COSINE. Delete the collection and re-ingest to fix. "
            f"This is an immutable collection property."
        )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    FastAPI lifespan — runs at startup and shutdown.
    Startup: telemetry → probe embedding dim → bootstrap Qdrant collection.
    Shutdown: (nothing needed — Qdrant client has no persistent connection to close).
    """
    settings = get_settings()

    # Telemetry (gracefully skips if Phoenix is not running)
    setup_tracing()

    openrouter = AsyncOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=settings.openrouter_api_key,
        default_headers={
            "HTTP-Referer": "https://privacy-policy-assistant",
            "X-OpenRouter-Title": "Privacy Policy Assistant",
        },
    )
    qdrant = AsyncQdrantClient(
        host=settings.qdrant_host,
        port=settings.qdrant_port,
        api_key=settings.qdrant_api_key,
    )

    dim = await _probe_embedding_dim(
        openrouter, "nvidia/llama-nemotron-embed-vl-1b-v2"
    )
    await _ensure_collection(qdrant, dim)

    print("[startup] FastAPI ready.")
    yield
    # Shutdown — nothing to close


def create_app() -> FastAPI:
    return FastAPI(
        title="Privacy Policy Compliance Assistant",
        description="RAG-based chatbot for privacy policy Q&A with inline citations.",
        version="0.1.0",
        lifespan=lifespan,
    )


app = create_app()


@app.get("/health")
async def health() -> dict:
    """
    Liveness probe — returns 200 if the service is running.
    Does NOT check Qdrant connectivity (that is verified at startup).
    """
    return {"status": "ok"}
```

Note: `asyncio.run()` is intentionally NOT used inside the lifespan — all async calls use `await` directly within the already-running asyncio event loop (AI-SPEC §4b.2 critical mistake avoidance).
  </action>
  <verify>
    <automated>grep "asynccontextmanager" D:/data/code/privacy-policy-compliance-assistant/backend/app/main.py && grep "Distance.COSINE" D:/data/code/privacy-policy-compliance-assistant/backend/app/main.py && grep "probe_embedding_dim\|_probe_embedding_dim" D:/data/code/privacy-policy-compliance-assistant/backend/app/main.py && grep "RuntimeError" D:/data/code/privacy-policy-compliance-assistant/backend/app/main.py && grep "setup_tracing" D:/data/code/privacy-policy-compliance-assistant/backend/app/core/telemetry.py</automated>
  </verify>
  <done>main.py has lifespan with probe → ensure_collection → COSINE guard → yield. Does not call asyncio.run() inside lifespan. telemetry.py has setup_tracing() with graceful ImportError/Exception handling. /health endpoint returns {"status": "ok"}.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| .env → Settings() | pydantic-settings reads secrets at process startup |
| FastAPI startup → OpenRouter API | API key sent over HTTPS to external service |
| FastAPI startup → Qdrant | Internal Docker network call to create/verify collection |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-03-01 | Information Disclosure | OPENROUTER_API_KEY in Settings | mitigate | Loaded from .env at startup; never logged or returned in any API response; @lru_cache means it is read once |
| T-03-02 | Denial of Service | Missing required env vars | mitigate | pydantic-settings raises ValidationError at startup if OPENROUTER_API_KEY or JWT_SECRET are absent — service refuses to start rather than running broken |
| T-03-03 | Tampering | Wrong Qdrant distance metric | mitigate | Post-creation guard in _ensure_collection raises RuntimeError if distance != COSINE — prevents silent wrong-metric operation (AI-SPEC §6 guardrail, Pitfall C1) |
| T-03-04 | Elevation of Privilege | JWT_SECRET weak or short | accept | Validation of minimum 32-char length is a Phase 3 concern (AUTH-05); loaded at startup; documented in .env.example comment |
| T-03-05 | Information Disclosure | Telemetry data sent to Phoenix | accept | Phoenix runs locally in Docker Compose — no data leaves the local network; traces contain OpenAI API calls but not user content at Phase 1 |
</threat_model>

<verification>
After Plan 03 completes:
- `python -c "from backend.app.core.config import get_settings"` resolves without ImportError (requires .venv with pydantic-settings installed)
- `grep "class Settings(BaseSettings)" backend/app/core/config.py` returns a match
- `grep "asyncio.run" backend/app/main.py` returns empty (no asyncio.run inside lifespan)
- `grep "Distance.COSINE" backend/app/main.py` returns at least 2 matches (creation + guard)
- `grep "@lru_cache" backend/app/core/config.py` returns a match
- Starting the backend locally with `uvicorn backend.app.main:app --reload` fails fast with a clear ValidationError if `.env` is missing OPENROUTER_API_KEY
</verification>

<success_criteria>
- config.py: Settings(BaseSettings) with openrouter_api_key and jwt_secret as required fields; get_settings() with @lru_cache
- telemetry.py: setup_tracing() gracefully handles ImportError and connection failures (Phoenix may not run in local dev)
- main.py: lifespan probes embedding dim → creates/verifies policies collection with COSINE → raises RuntimeError on wrong metric
- /health endpoint returns 200 {"status": "ok"}
- No asyncio.run() calls inside the lifespan context manager
</success_criteria>

<output>
After completion, create `.planning/phases/01-infrastructure-data-ingestion/01-03-SUMMARY.md` with:
- Settings fields defined and their types
- Lifespan startup sequence confirmed
- /health endpoint URL
- Any deviations from the plan and why
</output>
