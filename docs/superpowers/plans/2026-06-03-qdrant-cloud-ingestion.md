# Qdrant Cloud Ingestion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ensure ingestion writes to Qdrant Cloud by requiring `QDRANT_URL` and `QDRANT_API_KEY` and using the URL-based Qdrant client.

**Architecture:** The ingestion module validates cloud connection settings at startup, constructs an `AsyncQdrantClient` with the full URL and API key, and uses that client for collection setup, upserts, and sanity checks. The rest of the ingestion pipeline (embed → upsert → checkpoint) remains unchanged.

**Tech Stack:** Python 3.11, pydantic-settings, qdrant-client, pytest

---

## File Structure
- Create: `backend/ingestion/tests/test_ingest_cloud_config.py` — unit tests for cloud settings validation and client initialization.
- Modify: `backend/app/core/config.py` — add `qdrant_url` setting (env: `QDRANT_URL`).
- Modify: `backend/ingestion/ingest.py` — require `QDRANT_URL`/`QDRANT_API_KEY` and build the client via URL.
- Modify: `README.md` — document cloud ingestion env vars and update ingest instructions.

---

### Task 1: Cloud Qdrant settings validation and client initialization

**Files:**
- Create: `backend/ingestion/tests/test_ingest_cloud_config.py`
- Modify: `backend/app/core/config.py`
- Modify: `backend/ingestion/ingest.py`
- Test: `backend/ingestion/tests/test_ingest_cloud_config.py`

- [ ] **Step 1: Write the failing tests**

```python
# backend/ingestion/tests/test_ingest_cloud_config.py
import os
from unittest.mock import patch

import pytest

from backend.app.core.config import Settings

os.environ.setdefault("OPENROUTER_API_KEY", "test-openrouter-key")
os.environ.setdefault("JWT_SECRET", "x" * 32)
os.environ.setdefault("QDRANT_URL", "https://cluster.qdrant.io")
os.environ.setdefault("QDRANT_API_KEY", "qdrant_key")

from backend.ingestion import ingest


def _make_settings(**overrides) -> Settings:
    return Settings(
        openrouter_api_key="test-openrouter-key",
        jwt_secret="x" * 32,
        qdrant_url=overrides.get("qdrant_url"),
        qdrant_api_key=overrides.get("qdrant_api_key"),
    )


def test_require_qdrant_cloud_settings_missing_url():
    settings = _make_settings(qdrant_url=None, qdrant_api_key="qdrant_key")
    with pytest.raises(RuntimeError, match="QDRANT_URL"):
        ingest._require_qdrant_cloud_settings(settings)


def test_require_qdrant_cloud_settings_missing_api_key():
    settings = _make_settings(qdrant_url="https://cluster.qdrant.io", qdrant_api_key=None)
    with pytest.raises(RuntimeError, match="QDRANT_API_KEY"):
        ingest._require_qdrant_cloud_settings(settings)


def test_make_qdrant_client_uses_url_and_api_key():
    settings = _make_settings(
        qdrant_url="https://cluster.qdrant.io",
        qdrant_api_key="qdrant_key",
    )
    with patch("backend.ingestion.ingest.AsyncQdrantClient") as mock_client:
        ingest._make_qdrant_client(settings)
    mock_client.assert_called_once_with(
        url="https://cluster.qdrant.io",
        api_key="qdrant_key",
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/ingestion/tests/test_ingest_cloud_config.py -v`  
Expected: FAIL with `AttributeError` for missing `_require_qdrant_cloud_settings` / `_make_qdrant_client`.

- [ ] **Step 3: Add `qdrant_url` to settings**

```python
# backend/app/core/config.py (add near other Qdrant settings)
    # Qdrant connection — QDRANT_URL is required for cloud ingestion
    qdrant_url: str | None = None
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_api_key: str | None = None
```

- [ ] **Step 4: Implement cloud URL validation and client construction**

```python
# backend/ingestion/ingest.py (replace the Qdrant client block)
from backend.app.core.config import Settings, get_settings

settings = get_settings()

openrouter = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=settings.openrouter_api_key,
    default_headers={
        "HTTP-Referer": "https://github.com/privacy-policy-compliance-assistant",
        "X-Title": "Privacy Policy Compliance Assistant",
    },
)


def _require_qdrant_cloud_settings(settings: Settings) -> tuple[str, str]:
    url = (settings.qdrant_url or "").strip()
    api_key = (settings.qdrant_api_key or "").strip()
    if not url:
        raise RuntimeError("QDRANT_URL is required for ingestion. Set QDRANT_URL in .env.")
    if not api_key:
        raise RuntimeError("QDRANT_API_KEY is required for ingestion. Set QDRANT_API_KEY in .env.")
    return url, api_key


def _make_qdrant_client(settings: Settings) -> AsyncQdrantClient:
    url, api_key = _require_qdrant_cloud_settings(settings)
    return AsyncQdrantClient(url=url, api_key=api_key)


qdrant = _make_qdrant_client(settings)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest backend/ingestion/tests/test_ingest_cloud_config.py -v`  
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/core/config.py backend/ingestion/ingest.py backend/ingestion/tests/test_ingest_cloud_config.py
git commit -m "feat: require qdrant cloud settings for ingestion"
```

---

### Task 2: Update ingestion documentation

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update local setup env block and ingest instructions**

```markdown
# README.md (Local Setup > Configure environment variables)
OPENROUTER_API_KEY=your-openrouter-key
JWT_SECRET=generate-a-secret-at-least-32-characters
ADMIN_USERNAME=admin
ADMIN_PASSWORD=change-me-before-production
QDRANT_URL=https://example.us-east.aws.cloud.qdrant.io
QDRANT_API_KEY=qdrant_example_key

# (Optional) Backend overrides for local Qdrant
QDRANT_HOST=localhost
QDRANT_PORT=6333
```

```markdown
# README.md (Local Setup > Start Qdrant and ingest the corpus)
Ensure `QDRANT_URL` and `QDRANT_API_KEY` are set before running ingestion.
If ingesting into a local Qdrant instance, set `QDRANT_URL=http://localhost:6333`
and configure a local API key to match.
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: document qdrant cloud ingestion env vars"
```

---

## Plan Self-Review
- [ ] **Spec coverage:** Validates cloud URL + API key, updates ingest client, and updates docs.
- [ ] **Placeholder scan:** No TODO/TBD markers; all steps include explicit code/commands.
- [ ] **Type consistency:** `qdrant_url` uses `str | None` consistently in config and tests.
