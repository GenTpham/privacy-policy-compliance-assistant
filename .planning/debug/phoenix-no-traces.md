---
slug: phoenix-no-traces
status: resolved
trigger: "Phoenix observability không hoạt động - UI mở được nhưng 0 traces/spans"
created: "2026-05-04"
updated: "2026-05-04"
---

# Debug Session: phoenix-no-traces

## Symptoms

- **Expected:** Phoenix UI (localhost:6006) hiển thị trace/span data từ backend khi user gọi API chat
- **Actual:** Phoenix UI mở được nhưng không có trace/span nào (0 traces), dù backend đang chạy
- **How to run:** `docker compose up` (không có `--profile observability`)
- **Error messages:** None reported — UI loads but empty
- **Timeline:** Unknown — may never have worked

## Current Focus

hypothesis: "Three compounding causes: (1) opentelemetry/openinference packages missing from requirements.txt so ImportError silently disables tracing; (2) backend service missing PHOENIX_COLLECTOR_ENDPOINT env var; (3) user ran without --profile observability so Phoenix container never started"
test: "Read requirements.txt, telemetry.py, docker-compose.yml, main.py"
expecting: "Missing packages = ImportError caught silently; no Phoenix container = nothing to export to"
next_action: "Fix applied — add OTel packages to requirements.txt, add phoenix_collector_endpoint to config, add depends_on to docker-compose"
reasoning_checkpoint: "All three causes confirmed from file reads"

## Evidence

- timestamp: 2026-05-04T00:00:00Z
  file: requirements.txt
  finding: "No opentelemetry-* or openinference-* packages listed. telemetry.py catches ImportError and prints '[telemetry] opentelemetry not installed — tracing disabled' — tracing is never initialized in the Docker container."

- timestamp: 2026-05-04T00:00:01Z
  file: backend/app/core/telemetry.py
  finding: "setup_tracing() defers all OTel imports inside try/except ImportError. Default endpoint hardcoded to 'http://phoenix:4317'. No way to configure endpoint from env var."

- timestamp: 2026-05-04T00:00:02Z
  file: backend/app/core/config.py
  finding: "No phoenix_collector_endpoint field in Settings. Endpoint is hardcoded in telemetry.py default arg — cannot be overridden via environment variable."

- timestamp: 2026-05-04T00:00:03Z
  file: docker-compose.yml
  finding: "backend service has no PHOENIX_COLLECTOR_ENDPOINT env var and no depends_on: phoenix. Phoenix service has no healthcheck. User ran without --profile observability so Phoenix container was never started."

- timestamp: 2026-05-04T00:00:04Z
  file: backend/app/main.py
  finding: "setup_tracing() called with no arguments — uses hardcoded default 'http://phoenix:4317'. Even with Phoenix running, if packages are missing, ImportError is swallowed silently."

## Eliminated

- Phoenix UI broken: eliminated — UI loads fine at localhost:6006
- Network misconfiguration: eliminated — phoenix service uses correct container name 'phoenix' and port 4317 for OTLP/gRPC

## Resolution

root_cause: "Three compounding causes: (1) opentelemetry-sdk, opentelemetry-exporter-otlp-proto-grpc, and openinference-instrumentation-openai packages are absent from requirements.txt, causing a silent ImportError that disables all tracing; (2) the Phoenix collector endpoint is hardcoded with no env-var override path through Settings; (3) the backend docker-compose service has no depends_on: phoenix so startup order is not guaranteed when using the observability profile."
fix: "Add the three missing OTel/OpenInference packages to requirements.txt; add phoenix_collector_endpoint to Settings with default 'http://phoenix:4317'; pass settings value into setup_tracing(); add phoenix healthcheck and backend depends_on condition to docker-compose.yml."
verification: "docker compose --profile observability up --build; call a chat endpoint; check Phoenix UI at localhost:6006 for traces."
files_changed:
  - requirements.txt
  - backend/app/core/config.py
  - backend/app/core/telemetry.py
  - backend/app/main.py
  - docker-compose.yml
