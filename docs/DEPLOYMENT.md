# Deployment

What's needed to deploy PulseIQ, and — importantly — what's actually been
verified versus what's still a documented plan.

**Honesty check first: as of this writing, PulseIQ has not been deployed
to Railway or Vercel yet** — a target has been chosen (this document) and
every piece of it has been verified locally in a way that closely
simulates the real platform, but the actual dashboard-driven account setup
(creating the projects, connecting GitHub, pasting in environment
variables) requires the account owner's own hands — nothing here claims
that step has happened until it demonstrably has.

## Current deployment mode

**Local storage, run via Docker Compose or natively — not yet deployed to
a hosting platform.**

## Chosen deployment target

| Piece | Platform | Why |
|---|---|---|
| Backend (FastAPI) | **Railway** | Deploys straight from `backend/Dockerfile`; dashboard-driven GitHub integration (push → auto-deploy, no CLI/token needed); supports persistent volumes if local storage ever needs to survive redeploys. |
| Frontend (static Vite build) | **Vercel** | Already primed via its GitHub App; excellent fit for a plain SPA; push → auto-deploy. |
| Database | **Neon** (already in use) | No change — same Postgres this project has run against natively and via Docker throughout development. |
| Storage | **Local disk** (accepted limitation) | See `docs/STORAGE.md` — uploaded datasets may not survive a Railway redeploy. R2 remains a documented, ready-to-enable upgrade path whenever credentials are available. |

## Backend on Railway

**Requirements verified locally**, simulating Railway's exact runtime
contract (dynamic `$PORT`, no `docker-compose.yml` in the picture, a
fresh non-dev `SECRET_KEY`):

```bash
docker run --rm -e PORT=9500 -e DATABASE_URL=... -e ENVIRONMENT=production \
  -e DEBUG=false -e SECRET_KEY=<real secret> -p 9500:9500 <backend-image>
```

— migrations ran, uvicorn bound to the injected port (not the old
hardcoded 8000), health check returned 200, logs switched to JSON
(`DEBUG=false`). Two real gaps were found and fixed while verifying this
(not left for Railway to discover):

1. **The Dockerfile's own `CMD` never ran migrations** — only
   `docker-compose.yml`'s `command:` override did. Railway builds the
   Dockerfile directly, with no compose file involved, so it would have
   started serving traffic against un-migrated tables. Fixed: the
   migration step now lives in the image's own `CMD`, and
   `docker-compose.yml`'s override was removed as redundant.
2. **The container was hardcoded to port 8000** — Railway (like most
   PaaS platforms) injects a dynamic `PORT` env var and expects the
   container to bind to it. Fixed: `CMD`/`HEALTHCHECK` are now shell-form
   with `${PORT:-8000}`, so `$PORT` is honored when set (Railway) and
   8000 remains the default when nothing sets it (local Docker/compose —
   verified unchanged).

`backend/railway.json` is a config-as-code file that tells Railway to
build from `Dockerfile` and health-check `/api/v1/health` — it saves a few
manual dashboard fields but doesn't replace the steps below.

### Setup steps (dashboard — do this part yourself)

1. [railway.app](https://railway.app) → New Project → **Deploy from GitHub repo** → select `Aakif9866/PULSEIQ`.
2. In the new service's Settings → **Root Directory**: `backend`. Railway
   will pick up `backend/Dockerfile` and `backend/railway.json`
   automatically from there.
3. Add these environment variables (Settings → Variables):

   | Variable | Value |
   |---|---|
   | `DATABASE_URL` | Your Neon connection string (same one already in local `.env`) |
   | `ENVIRONMENT` | `production` |
   | `DEBUG` | `false` |
   | `SECRET_KEY` | A real, unique secret — **not** the local placeholder. A freshly generated one was produced while preparing this (see chat, not committed anywhere) — or generate your own: `python3 -c "import secrets; print(secrets.token_hex(32))"` |
   | `STORAGE_PROVIDER` | `local` |
   | `MAX_UPLOAD_SIZE_MB` | `200` |
   | `AI_PROVIDER` | `groq` |
   | `GROQ_API_KEY` | Your real key (same one already in local `.env`) |
   | `GROQ_MODEL` | `openai/gpt-oss-120b` |
   | `CORS_ORIGINS` | `["https://<your-vercel-app>.vercel.app"]` — fill in once the frontend step below gives you the real Vercel URL; a placeholder here until then just means CORS blocks the frontend, not a security hole |

   Do **not** set `PORT` — Railway injects it automatically.
4. Deploy. Railway gives you a URL like `https://pulseiq-backend-production.up.railway.app` — copy it, it's needed for the frontend step.
5. Confirm it's alive: `curl https://<your-railway-url>/api/v1/health` should return `{"status":"ok","storage_provider":"local"}`.

## Frontend on Vercel

No code changes needed — `frontend/src/lib/api-client.ts` already reads
`VITE_API_URL` at build time (`import.meta.env.VITE_API_URL ?? '/api/v1'`),
which is exactly the mechanism a split-host (frontend and backend on
different domains) deployment needs; this was verified by inspection, not
added for this.

### Setup steps (dashboard — do this part yourself)

1. In your already-pending Vercel project for this repo: Settings → **Root
   Directory**: `frontend`. Vercel should auto-detect the Vite framework
   preset (build command `npm run build`, output directory `dist`).
2. Add an environment variable: `VITE_API_URL` =
   `https://<your-railway-url>/api/v1` (the URL from the backend step,
   with `/api/v1` appended — the same path prefix `API_V1_PREFIX` uses
   everywhere else).
3. Deploy. Vercel gives you a URL like `https://pulseiq.vercel.app`.
4. **Go back to Railway** and set `CORS_ORIGINS` to include this real URL,
   e.g. `["https://pulseiq.vercel.app"]` — the backend's default
   (`localhost` only) will otherwise block every request from the deployed
   frontend with a CORS error, not a helpful one.

## Local storage limitation

Covered in full in `docs/STORAGE.md` — the short version: Railway's
filesystem is ephemeral across redeploys unless a persistent volume is
attached. **Uploaded datasets will not survive a redeploy** in this
configuration — accepted as a known limitation for now (see the
`AskUserQuestion` decision this deployment was built against), not an
oversight. Two ways to change that later, neither requiring a code
change: attach a Railway volume mounted at `LOCAL_STORAGE_ROOT`, or switch
`STORAGE_PROVIDER` to `r2` once Cloudflare credentials are available.

## Database requirements

Unchanged from before — any real Postgres works; this project has run
against a local Homebrew-installed Postgres 16 and a live Neon instance
with no code differences. Migrations (`backend/alembic/versions/`) are
the only schema-management mechanism.

## Verified vs. not yet verified

**Verified locally**, standing in for the real platforms as closely as
possible:
- The exact Railway runtime contract (dynamic `$PORT`, Dockerfile-only
  build, no compose file, a real non-placeholder `SECRET_KEY`,
  `ENVIRONMENT=production`) — via `docker run` with those exact
  conditions, not just `docker compose up`.
- `docker-compose.yml` still works identically after removing its now-
  redundant `command:` override (regression-checked: both containers
  build and report `healthy`, a real signup round-tripped through the
  containerized nginx proxy, same as before).
- The frontend's `VITE_API_URL` mechanism, by reading the code — not yet
  built with a real non-default value and deployed to check the bundled
  output calls the right host.

**Not yet verified** (genuinely, not hidden):
- An actual deployment to Railway or Vercel's real infrastructure.
- The real cross-origin request from a deployed Vercel frontend to a
  deployed Railway backend (the CORS configuration above is correct by
  inspection of `app/core/config.py`'s `CORS_ORIGINS` handling, not by
  having watched a real browser request succeed against it).
- Railway's actual ephemeral-storage behavior across a real redeploy
  (documented as expected behavior for this class of platform, not
  observed directly on Railway specifically).
