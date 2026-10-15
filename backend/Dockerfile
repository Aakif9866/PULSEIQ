# Two stages: compilers live only in the build stage; the runtime image
# gets the installed virtualenv and runs as an unprivileged user.
FROM python:3.12-slim AS build

ENV PIP_NO_CACHE_DIR=1

# Build deps for any wheel that has to compile from source on slim images.
RUN apt-get update && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY requirements.txt .
RUN pip install -r requirements.txt


FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

RUN useradd --create-home --uid 10001 app
WORKDIR /app
COPY --from=build /opt/venv /opt/venv
COPY --chown=app:app . .
# Local-storage uploads (dev / Docker Compose) need a writable directory.
RUN mkdir -p /app/data/uploads && chown -R app:app /app/data
USER app

EXPOSE 8000

# Python instead of curl, so the runtime image needs no extra packages.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://localhost:{os.environ.get(\"PORT\", \"8000\")}/api/v1/health', timeout=4)"

# Shell form so $PORT expands (Render injects PORT; 8000 is the default for
# Docker Compose and plain `docker run`). Migrations run first, so the image
# is correct standalone. The demo seeder is a no-op unless DEMO_USER_EMAIL/
# DEMO_USER_PASSWORD are set; its `|| true` is deliberate: a broken demo
# must never stop the API from booting, while a failed migration still should.
# ponytail: migrations at boot are safe with one instance; run them as a
# separate release step before scaling to several.
CMD ["sh", "-c", "alembic upgrade head && (python -m app.workers.seed_demo || true) && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
