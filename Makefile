.PHONY: venv install install-dev qdrant-up qdrant-down ingest eval-ingest eval-ingest-fast dev up down health smoke-test

# ── Environment setup ─────────────────────────────────────────────────────────
venv:
	python3.11 -m venv .venv

install:
	.venv/bin/pip install -r requirements.txt

install-dev:
	.venv/bin/pip install -r requirements.txt -r requirements-dev.txt

# ── Local dev: Qdrant only (D-05 workflow) ────────────────────────────────────
qdrant-up:
	docker compose up qdrant -d

qdrant-down:
	docker compose down

# ── Data ingestion ────────────────────────────────────────────────────────────
ingest:
	.venv/bin/python -m backend.ingestion.ingest

# ── Eval targets (from AI-SPEC §5) ───────────────────────────────────────────
eval-ingest:
	.venv/bin/pytest backend/ingestion/tests/test_ingestion_evals.py -v --tb=short

eval-ingest-fast:
	.venv/bin/pytest backend/ingestion/tests/test_ingestion_evals.py -v --tb=short \n	  -k "not rank1 and not embedding_dim and not resumability and not persistence"

# ── Local backend dev ─────────────────────────────────────────────────────────
dev:
	.venv/bin/uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000

# ── Docker full stack ─────────────────────────────────────────────────────────
up:
	docker compose up

down:
	docker compose down

# ── Health check ──────────────────────────────────────────────────────────────
health:
	curl -f http://localhost:8000/health && curl -f http://localhost:6333/readyz

# ── Smoke test: start full stack and verify health ────────────────────────────
smoke-test:
	docker compose up -d --build
	@echo "Waiting for backend /health (up to 60s)..."
	curl -f --retry 12 --retry-delay 5 --retry-connrefused http://localhost:8000/health \
	  && echo "PASS: backend healthy" || (echo "FAIL: backend unhealthy" && exit 1)
	@echo "Waiting for frontend (up to 60s)..."
	curl -f --retry 12 --retry-delay 5 --retry-connrefused http://localhost:80 \
	  && echo "PASS: frontend healthy" || (echo "FAIL: frontend unhealthy" && exit 1)
	@echo "smoke-test PASSED"
