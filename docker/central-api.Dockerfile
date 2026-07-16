FROM ghcr.io/astral-sh/uv:0.8.22 AS uv
FROM python:3.11-slim AS runtime
RUN apt-get update && apt-get install -y --no-install-recommends tini && rm -rf /var/lib/apt/lists/*
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app
COPY packages/trackflow_auth packages/trackflow_auth
COPY packages/trackflow_incidents packages/trackflow_incidents
COPY data data
COPY services/central-api services/central-api
WORKDIR /app/services/central-api
RUN uv sync --frozen --no-dev && useradd --system --uid 10001 --create-home trackflow && chown -R trackflow:trackflow /app
USER 10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/live', timeout=3)"]
ENTRYPOINT ["tini", "--"]
CMD [".venv/bin/uvicorn", "central_api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
