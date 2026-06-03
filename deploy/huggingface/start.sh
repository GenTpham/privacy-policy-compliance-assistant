#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/home/user/app"
QDRANT_DIR="/qdrant"
QDRANT_STORAGE="/data/qdrant"
BACKEND_DATA="/data/backend"

mkdir -p "$QDRANT_STORAGE" "$BACKEND_DATA"

rm -rf "$QDRANT_DIR/storage"
ln -s "$QDRANT_STORAGE" "$QDRANT_DIR/storage"

rm -rf "$APP_DIR/backend/data"
ln -s "$BACKEND_DATA" "$APP_DIR/backend/data"

export QDRANT_HOST="${QDRANT_HOST:-127.0.0.1}"
export QDRANT_PORT="${QDRANT_PORT:-6333}"

cd "$QDRANT_DIR"
./qdrant &
QDRANT_PID=$!

for _ in $(seq 1 60); do
    if curl -fsS "http://127.0.0.1:6333/readyz" >/dev/null; then
        break
    fi
    sleep 1
done

if ! curl -fsS "http://127.0.0.1:6333/readyz" >/dev/null; then
    echo "Qdrant failed to become ready." >&2
    kill "$QDRANT_PID" 2>/dev/null || true
    exit 1
fi

cd "$APP_DIR"
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 &
API_PID=$!

for _ in $(seq 1 90); do
    if curl -fsS "http://127.0.0.1:8000/health" >/dev/null; then
        break
    fi
    sleep 1
done

if ! curl -fsS "http://127.0.0.1:8000/health" >/dev/null; then
    echo "FastAPI failed to become ready." >&2
    kill "$API_PID" "$QDRANT_PID" 2>/dev/null || true
    exit 1
fi

mkdir -p /tmp/nginx/client_body \
         /tmp/nginx/proxy_temp \
         /tmp/nginx/fastcgi_temp \
         /tmp/nginx/uwsgi_temp \
         /tmp/nginx/scgi_temp

nginx -g "daemon off;" &
NGINX_PID=$!

shutdown() {
    kill "$NGINX_PID" "$API_PID" "$QDRANT_PID" 2>/dev/null || true
    wait "$NGINX_PID" "$API_PID" "$QDRANT_PID" 2>/dev/null || true
}

trap shutdown INT TERM

wait -n "$NGINX_PID" "$API_PID" "$QDRANT_PID"
STATUS=$?
shutdown
exit "$STATUS"
