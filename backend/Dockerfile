FROM python:3.11-slim

# Install curl for healthcheck debugging
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements first for Docker layer caching
COPY requirements.txt .

# Install directly into system Python — no venv in Docker (Pitfall M6)
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source (build context is project root, see docker-compose.yml)
COPY backend/ ./backend/

# Expose backend port
EXPOSE 8000

# Production command — no --reload (Decision D-06)
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
