FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./
COPY static/ ./static/

# Built-in defaults (copied to user config on first run)
COPY config/leagues/ ./defaults/leagues/
COPY config/settings.yaml.default ./defaults/settings.yaml

# Entrypoint populates user config with defaults if missing
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

EXPOSE 8080

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
