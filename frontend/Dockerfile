# Stage 1: Build — node:20-alpine produces dist/
FROM node:20-alpine AS builder

# VITE_API_URL baked into the JS bundle at npm run build time (D-03)
# Default is /api — correct for Docker Compose (nginx proxies /api/* to backend)
# Override at build time: docker build --build-arg VITE_API_URL=http://localhost:8000
ARG VITE_API_URL=/api
ENV VITE_API_URL=${VITE_API_URL}

WORKDIR /app

# Copy dependency manifests first — Docker layer cache optimization (mirrors backend/Dockerfile pattern)
COPY package.json package-lock.json ./
RUN npm ci

# Copy application source after dependencies
COPY . .
RUN npm run build

# Stage 2: Serve — nginx:alpine serves the static bundle
FROM nginx:alpine

# Copy built assets from Stage 1
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy nginx reverse proxy config
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
# nginx runs as the default CMD — no explicit CMD override needed
