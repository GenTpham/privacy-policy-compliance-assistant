---
id: 01-PLAN-01
wave: 1
depends_on: []
phase: 01-infrastructure-data-ingestion
goal: Create project directory structure, dependency pinning, secrets template, and ignore files
files_modified:
  - requirements.txt
  - requirements-dev.txt
  - .env.example
  - .gitignore
  - .dockerignore
  - backend/__init__.py
  - backend/app/__init__.py
  - backend/app/core/__init__.py
  - backend/ingestion/__init__.py
  - backend/ingestion/tests/__init__.py
autonomous: true
requirements:
  - INFRA-03
  - INFRA-05
---

<objective>
Establish the project skeleton that every subsequent plan depends on: directory layout, pinned runtime dependencies, `.env.example` secrets template, and ignore files that prevent `.venv` or secrets from entering Docker or git.

Purpose: Plans 02–05 all assume these files exist. The directory structure defined here (per AI-SPEC §3 Recommended Project Structure) must be in place before any Python or Docker work begins.
Output: requirements.txt, requirements-dev.txt, .env.example, .gitignore, .dockerignore, and empty `__init__.py` package markers.
</objective>

<execution_context>
@D:\data\code\privacy-policy-compliance-assistant\.planning\phases\01-infrastructure-data-ingestion\01-AI-SPEC.md
</execution_context>

<context>
@D:\data\code\privacy-policy-compliance-assistant\.planning\ROADMAP.md
@D:\data\code\privacy-policy-compliance-assistant\.planning\phases\01-infrastructure-data-ingestion\01-CONTEXT.md

<interfaces>
<!-- Dataset file confirmed at: dataset/json/train/policy_qa_train.json -->
<!-- Record shape: {"id": str, "title": str, "context": str, "question": str, "answers": {...}} -->
<!-- Settings fields required by AI-SPEC §4b.1: -->
<!--   openrouter_api_key: str          (required, no default) -->
<!--   qdrant_host: str = "localhost"   (override to "qdrant" in Docker Compose) -->
<!--   qdrant_port: int = 6333 -->
<!--   qdrant_api_key: str | None = None -->
<!--   jwt_secret: str                  (required, no default) -->
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create pinned dependency files</name>
  <files>requirements.txt, requirements-dev.txt</files>
  <read_first>
    - D:\data\code\privacy-policy-compliance-assistant\.planning\phases\01-infrastructure-data-ingestion\01-AI-SPEC.md (§3 Installation section — exact package versions)
    - D:\data\code\privacy-policy-compliance-assistant\.planning\research\STACK.md (Key Library Details — Installation section)
  </read_first>
  <action>
Create `requirements.txt` with these exact pinned versions (per AI-SPEC §3 and STACK.md):

```
fastapi==0.136.0
uvicorn[standard]
qdrant-client==1.17.1
openai==2.32.0
pydantic-settings>=2.0
tiktoken
PyJWT
pwdlib[argon2]
sqlalchemy[asyncio]
aiosqlite
python-multipart
```

Create `requirements-dev.txt` (dev-only extras, not in production image):
```
pytest
pytest-asyncio
httpx
```

Do NOT include `langchain`, `llama-index`, `passlib`, `python-jose`, or `bcrypt` — all explicitly prohibited or deprecated per CLAUDE.md and STACK.md.
  </action>
  <verify>
    <automated>grep -E "^fastapi==0\.136\.0" D:/data/code/privacy-policy-compliance-assistant/requirements.txt && grep -E "^qdrant-client==1\.17\.1" D:/data/code/privacy-policy-compliance-assistant/requirements.txt && grep -E "^openai==2\.32\.0" D:/data/code/privacy-policy-compliance-assistant/requirements.txt && grep "tiktoken" D:/data/code/privacy-policy-compliance-assistant/requirements.txt && grep "pydantic-settings" D:/data/code/privacy-policy-compliance-assistant/requirements.txt</automated>
  </verify>
  <done>requirements.txt contains all 11 pinned packages; requirements-dev.txt contains pytest, pytest-asyncio, httpx. Neither file contains langchain, llama-index, passlib, or python-jose.</done>
</task>

<task type="auto">
  <name>Task 2: Create .env.example, .gitignore, and .dockerignore</name>
  <files>.env.example, .gitignore, .dockerignore</files>
  <read_first>
    - D:\data\code\privacy-policy-compliance-assistant\.planning\phases\01-infrastructure-data-ingestion\01-CONTEXT.md (D-07: .venv in .dockerignore; D-14: secret variable names)
    - D:\data\code\privacy-policy-compliance-assistant\.planning\phases\01-infrastructure-data-ingestion\01-AI-SPEC.md (§4b.1 Settings class — field names)
  </read_first>
  <action>
Create `.env.example` with placeholder values matching the exact field names from the pydantic-settings `Settings` class (per D-14 and AI-SPEC §4b.1):

```
# OpenRouter API key — get from https://openrouter.ai/settings/keys
OPENROUTER_API_KEY=your-openrouter-api-key-here

# Qdrant connection — use "localhost" for local dev, "qdrant" inside Docker Compose
QDRANT_HOST=localhost
QDRANT_PORT=6333
# Optional: leave blank for unauthenticated local Qdrant
QDRANT_API_KEY=

# JWT secret — generate with: openssl rand -hex 32
# REQUIRED: minimum 32 characters
JWT_SECRET=change-me-generate-with-openssl-rand-hex-32
```

Create `.gitignore` containing at minimum:
```
.env
.venv/
__pycache__/
*.pyc
*.pyo
ingestion_checkpoint.json
*.db
*.sqlite
.DS_Store
```

Create `.dockerignore` containing at minimum (per D-07 and M6):
```
.venv/
.git/
.gitignore
*.md
.env
ingestion_checkpoint.json
__pycache__/
*.pyc
*.pyo
*.db
*.sqlite
.planning/
dataset/
```

The `dataset/` directory is excluded from Docker builds — it is read by the ingestion script running locally, not by the FastAPI container.
  </action>
  <verify>
    <automated>grep "OPENROUTER_API_KEY" D:/data/code/privacy-policy-compliance-assistant/.env.example && grep "JWT_SECRET" D:/data/code/privacy-policy-compliance-assistant/.env.example && grep "\.venv/" D:/data/code/privacy-policy-compliance-assistant/.gitignore && grep "\.venv/" D:/data/code/privacy-policy-compliance-assistant/.dockerignore && grep "ingestion_checkpoint\.json" D:/data/code/privacy-policy-compliance-assistant/.gitignore</automated>
  </verify>
  <done>.env.example has OPENROUTER_API_KEY, QDRANT_HOST, QDRANT_PORT, QDRANT_API_KEY, JWT_SECRET with placeholder values. .gitignore includes .env, .venv/, ingestion_checkpoint.json. .dockerignore includes .venv/, .env, ingestion_checkpoint.json, dataset/.</done>
</task>

<task type="auto">
  <name>Task 3: Create directory structure and __init__.py package markers</name>
  <files>
    backend/__init__.py,
    backend/app/__init__.py,
    backend/app/core/__init__.py,
    backend/ingestion/__init__.py,
    backend/ingestion/tests/__init__.py
  </files>
  <read_first>
    - D:\data\code\privacy-policy-compliance-assistant\.planning\phases\01-infrastructure-data-ingestion\01-AI-SPEC.md (§3 Recommended Project Structure)
  </read_first>
  <action>
Create the following directory structure by writing empty `__init__.py` files (each file contains only a single-line docstring comment):

- `backend/__init__.py` — content: `"""Privacy Policy Compliance Assistant — backend package."""`
- `backend/app/__init__.py` — content: `"""FastAPI application package."""`
- `backend/app/core/__init__.py` — content: `"""Core config and shared utilities."""`
- `backend/ingestion/__init__.py` — content: `"""Offline ingestion pipeline."""`
- `backend/ingestion/tests/__init__.py` — content: `"""Ingestion eval test suite."""`

This creates the module hierarchy required for `python -m backend.ingestion.ingest` to work (per AI-SPEC entry point pattern).

Do NOT create `backend/Dockerfile` yet — that is Plan 02's scope (Docker infrastructure).
Do NOT create `backend/app/main.py` yet — that is Plan 03's scope.
Do NOT create `backend/ingestion/ingest.py` yet — that is Plan 04's scope.
  </action>
  <verify>
    <automated>test -f D:/data/code/privacy-policy-compliance-assistant/backend/__init__.py && test -f D:/data/code/privacy-policy-compliance-assistant/backend/app/__init__.py && test -f D:/data/code/privacy-policy-compliance-assistant/backend/app/core/__init__.py && test -f D:/data/code/privacy-policy-compliance-assistant/backend/ingestion/__init__.py && test -f D:/data/code/privacy-policy-compliance-assistant/backend/ingestion/tests/__init__.py</automated>
  </verify>
  <done>All five __init__.py files exist in the correct directories. Running `python -m backend.ingestion.ingest` from project root would resolve the module path correctly (the script itself is created in Plan 04).</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| .env → process environment | Secrets are loaded from .env file; if .env is committed to git, secrets are leaked |
| .venv binaries → Docker build | Platform-incompatible binaries from a Windows .venv would corrupt the Linux container if .dockerignore is missing |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-01-01 | Information Disclosure | .env file | mitigate | .gitignore includes `.env` (exact filename, no wildcard gaps); .env.example commits only placeholder values, never real keys |
| T-01-02 | Information Disclosure | JWT_SECRET in .env.example | mitigate | .env.example value is a clearly labeled placeholder `change-me-generate-with-openssl-rand-hex-32`; instructions to use `openssl rand -hex 32` included in comment |
| T-01-03 | Tampering | requirements.txt dependency chain | accept | All packages pinned to exact versions; low risk for this internal tool; supply-chain hash-pinning is v2 concern |
| T-01-04 | Information Disclosure | ingestion_checkpoint.json | mitigate | .gitignore includes `ingestion_checkpoint.json` — checkpoint may contain hash values of indexed text; not high-risk but correctly excluded |
</threat_model>

<verification>
After Plan 01 completes:
- `cat requirements.txt` shows fastapi==0.136.0, qdrant-client==1.17.1, openai==2.32.0, tiktoken, pydantic-settings
- `grep -c "langchain\|llama.index\|passlib\|python-jose" requirements.txt` returns 0
- `cat .env.example` shows all 5 required env var names with placeholder values
- `cat .gitignore | grep .env` shows `.env` is gitignored
- `cat .dockerignore | grep ".venv"` shows `.venv/` is excluded from Docker builds
- All 5 `__init__.py` files exist
</verification>

<success_criteria>
- requirements.txt contains all required pinned packages; no prohibited packages
- .env.example contains OPENROUTER_API_KEY, QDRANT_HOST, QDRANT_PORT, QDRANT_API_KEY, JWT_SECRET with placeholder values
- .gitignore prevents .env and ingestion_checkpoint.json from being committed
- .dockerignore prevents .venv/ and dataset/ from entering the Docker build context
- Python package structure (backend/app/core, backend/ingestion/tests) created with __init__.py markers
</success_criteria>

<output>
After completion, create `.planning/phases/01-infrastructure-data-ingestion/01-01-SUMMARY.md` with:
- Files created and their purpose
- Package structure established
- Any deviations from the plan and why
</output>
