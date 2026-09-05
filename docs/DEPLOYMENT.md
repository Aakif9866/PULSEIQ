# Deployment

What's needed to deploy PulseIQ, and — importantly — what's actually been
verified versus what's still a documented plan.

**Honesty check first: PulseIQ has not been deployed to any cloud hosting
platform.** Fly.io, Railway, and similar targets were deliberately deferred
(`PHASES.md` Phase 6 — the user chose "skip for now" when asked). What
*has* been verified: running the full stack locally via Docker Compose,
end-to-end, against a real external Postgres (Neon). This document
describes that verified setup and what a real cloud deployment would
still need — it does not claim one has happened.

## Current deployment mode

**Local storage, run via Docker Compose or natively — not deployed to a
hosting platform.**

## Backend deployment requirements

- Python 3.12 (pinned in `backend/Dockerfile`, matches `pyproject.toml`'s
  `target-version`).
- A reachable PostgreSQL instance (14+; tested against Postgres 16 locally
  and against a live Neon instance) — `DATABASE_URL` accepts a standard
  connection string from any provider (`postgresql://` is normalized to
  the installed `psycopg` v3 driver automatically; see `docs/BUGS.md`
  BUG-001).
- `alembic upgrade head` must run before the app serves traffic — the
  Docker image's `command` already does this
  (`sh -c "alembic upgrade head && uvicorn ..."`).
- Environment variables — see `.env.example` for the full, current list:
  `ENVIRONMENT`, `DEBUG`, `SECRET_KEY` (the production-safety guard in
  `app/core/config.py` refuses to start if this is left at its insecure
  default with `ENVIRONMENT=production`), `DATABASE_URL`,
  `STORAGE_PROVIDER` (+ `LOCAL_STORAGE_ROOT` or the four `R2_*` values),
  `MAX_UPLOAD_SIZE_MB`, `AI_PROVIDER` (+ `GROQ_API_KEY`/`GROQ_MODEL` if
  `groq`), `CORS_ORIGINS` (must include the real deployed frontend origin
  — the default is `localhost` only).

## Frontend deployment requirements

- Node 22 to build (`frontend/Dockerfile`); the build output is static
  files served by nginx (`nginx.conf`) — no Node runtime needed after
  build.
- The bundled nginx config proxies `/api/*` to the backend service inside
  the same Docker network (`proxy_pass http://backend:8000/api/`) — a
  non-Docker-Compose deployment (frontend and backend on separate hosts)
  would need this adjusted to the backend's real reachable URL, or set
  `VITE_API_URL` at build time instead.
- No server-side rendering; it's a single-page app with client-side
  routing (`try_files $uri /index.html` handles refresh-on-a-subroute).

## Database requirements

Any real Postgres works — this project has been run against a local
Homebrew-installed Postgres 16 and a live Neon instance in the same
session, with no code differences between the two. Migrations
(`backend/alembic/versions/`) are the only schema-management mechanism;
there's no separate schema-sync step.

## Local storage limitation

Covered in full in `docs/STORAGE.md` — the short version: whether
uploaded files survive a restart or redeploy depends entirely on the
hosting platform's filesystem semantics (persistent volume vs. ephemeral
container disk). **Do not assume "deployed" means "uploads are safe"** —
verify the target platform's storage model, or switch to
`STORAGE_PROVIDER=r2` first if persistence matters and R2 credentials are
available.

## Docker deployment (verified locally)

`docker-compose.yml` defines two services — `backend`, `frontend` — no
local Postgres container (removed deliberately; both services read
`DATABASE_URL` from `.env` via `env_file`, pointing at whatever real
Postgres you configure — one database, not a local one to keep in sync
with a remote one). Verified locally: both images build cleanly, both
containers report `healthy` (a frontend container `HEALTHCHECK` bug was
found and fixed here — `docs/BUGS.md` BUG-005 — an IPv4/IPv6 loopback
mismatch, not a code-level app bug), and a real signup/login round-tripped
through the containerized nginx `/api` proxy to the backend container.

This has **not** been tested on any actual cloud container platform
(ECS, Cloud Run, Fly.io, Railway, a raw VM, etc.) — only on a local
machine. A real deployment would additionally need: a container registry
to push these images to, the platform's own env-var/secrets mechanism (see
`docs/SECURITY.md`), and a decision on the frontend's public origin for
`CORS_ORIGINS`.

## Recommended future production mode

**Cloudflare R2** for storage, once credentials are available — see
`docs/STORAGE.md`'s migration section for the exact four config values
and zero code changes required. A real deployment target (Fly.io,
Railway, or similar) is still an open decision — nothing here is written
against a specific platform's quirks yet, since none has been chosen.
