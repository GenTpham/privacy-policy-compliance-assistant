---
title: Privacy Policy Compliance Assistant
emoji: "\U0001F512"
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
pinned: false
---

# Privacy Policy Compliance Assistant

RAG chatbot for asking privacy-policy compliance questions with inline citations.

## Hugging Face Space Deployment

This repository supports the existing local Docker Compose deployment and a Hugging Face Docker Space demo deployment.

Hugging Face Spaces do not run `docker compose` directly, so the root `Dockerfile` runs Qdrant, FastAPI, nginx, and the built React app inside one container.

### Space Settings

Create a Docker Space and add these settings:

Secrets:

- `OPENROUTER_API_KEY`
- `JWT_SECRET` - at least 32 characters
- `ADMIN_PASSWORD`

Variables:

- `ADMIN_USERNAME=admin`
- `QDRANT_HOST=127.0.0.1`
- `QDRANT_PORT=6333`
- `RATE_LIMIT_PER_MINUTE=60`

### Persistence

Attach Hugging Face persistent storage for real use. The Space container stores:

- Qdrant data in `/data/qdrant`
- SQLite users DB in `/data/backend`

Without persistent storage, indexed passages and user accounts are lost when the Space restarts.

### Corpus Data

The Space image does not bundle the source dataset or a Qdrant snapshot. After first deploy, restore a Qdrant snapshot into `/data/qdrant` or run the ingestion command against the attached persistent storage before sharing the app.

### Push to a Space

```bash
huggingface-cli login
huggingface-cli repo create privacy-policy-compliance-assistant --type space --space_sdk docker --private
git remote add hf https://huggingface.co/spaces/<user>/privacy-policy-compliance-assistant
git push hf main
```
