# Quick Task 260519-hf-space-deploy: Hugging Face Space single-container deploy

## Goal

Add a Hugging Face Docker Space deployment path without changing the existing Docker Compose setup.

## Scope

- Add a root `Dockerfile` that builds the React frontend, installs the FastAPI backend, copies Qdrant from the official image, and runs on Hugging Face's single exposed port.
- Add a startup script that launches Qdrant, FastAPI, and nginx in one container.
- Add an nginx config for port `7860` with `/api`, `/auth`, and `/admin` reverse proxy support.
- Update README with Hugging Face Space metadata and deployment instructions.

## Verification

- Validate script/config syntax where possible.
- Build the Docker image locally if Docker is available.
