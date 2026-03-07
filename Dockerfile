# Stage 1: Build React frontend
FROM node:22-slim AS frontend-build

WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Python runtime
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends gosu && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./

# Copy built frontend from Stage 1
COPY --from=frontend-build /build/dist ./static/

# Built-in defaults (copied to user config on first run)
COPY config/leagues/ ./defaults/leagues/
COPY config/settings.yaml.default ./defaults/settings.yaml

# Entrypoint populates user config with defaults if missing
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# Non-root user (entrypoint runs as root for first-run config copy, then exec drops to appuser)
RUN adduser --disabled-password --no-create-home --gecos "" appuser

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/api/health')" || exit 1

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
