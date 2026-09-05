FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Build deps for psycopg / duckdb wheels on slim images
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8000

# Shell form (not exec-form CMD) so $PORT actually expands — most PaaS
# hosts (Railway included) inject a dynamic PORT and expect the container
# to bind to it; ${PORT:-8000} keeps 8000 as the default for docker-compose
# and plain `docker run`, where nothing sets PORT. Migrations run here
# too, so this image is correct standalone (Railway builds the Dockerfile
# directly, with no docker-compose.yml in the picture to supply that step).
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD sh -c 'curl -f http://localhost:${PORT:-8000}/api/v1/health || exit 1'

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
