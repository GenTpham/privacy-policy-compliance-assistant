FROM qdrant/qdrant:v1.17.1 AS qdrant

FROM node:20-alpine AS frontend-builder
ARG VITE_API_URL=
ENV VITE_API_URL=${VITE_API_URL}
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    QDRANT_HOST=127.0.0.1 \
    QDRANT_PORT=6333

RUN apt-get update \
    && apt-get install -y --no-install-recommends bash ca-certificates curl libunwind8 nginx tini tzdata \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 user

WORKDIR /home/user/app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --from=qdrant /qdrant /qdrant
COPY --from=frontend-builder --chown=user:user /app/dist ./frontend-dist
COPY --chown=user:user backend/ ./backend/
COPY deploy/huggingface/nginx.conf /etc/nginx/nginx.conf
COPY --chown=user:user deploy/huggingface/start.sh ./start.sh

RUN chmod +x ./start.sh \
    && mkdir -p /data/qdrant /data/backend /tmp/nginx/client_body /tmp/nginx/proxy /tmp/nginx/fastcgi /tmp/nginx/uwsgi /tmp/nginx/scgi \
    && chown -R user:user /data /home/user /qdrant /var/lib/nginx /var/log/nginx /tmp/nginx

EXPOSE 7860

USER user

CMD ["tini", "--", "./start.sh"]
