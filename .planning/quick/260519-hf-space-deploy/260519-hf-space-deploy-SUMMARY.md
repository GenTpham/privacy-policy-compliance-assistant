---
status: complete
quick_id: 260519-hf-space-deploy
---

# Quick Task 260519-hf-space-deploy Summary

## Completed

- Added a root Hugging Face Space `Dockerfile` that builds the React frontend, installs the FastAPI backend, copies Qdrant from `qdrant/qdrant:v1.17.1`, and exposes port `7860`.
- Added `deploy/huggingface/start.sh` to launch Qdrant, FastAPI, and nginx in one container.
- Added `deploy/huggingface/nginx.conf` to serve the SPA and proxy `/api`, `/auth`, `/admin`, and `/health`.
- Updated `README.md` with Hugging Face Space metadata, secrets/variables, persistence notes, and push commands.
- Fixed `CitationCard.test.tsx` fixtures so the frontend TypeScript build succeeds with the required `score` field.

## Verification

- `npm run build` passed in `frontend/`.
- `npm test -- CitationCard.test.tsx --run` passed.
- `bash -n deploy/huggingface/start.sh` passed.
- `python -m compileall -q backend` passed.
- `docker build -t privacy-policy-hf-space .` could not run because Docker Desktop's Linux daemon was not running on this machine.
