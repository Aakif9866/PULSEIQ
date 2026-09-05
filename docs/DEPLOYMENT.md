# Deployment

What's needed to deploy PulseIQ, and — importantly — what's actually been
verified versus what's still a documented plan.

**Honesty check first:** the backend is now genuinely deployed and live on
Railway — verified with a real HTTP request against the deployed URL, not
assumed (see "Backend on Railway" below). The frontend has **not** been
deployed yet; its setup steps below remain a documented plan until that
service actually exists and has been verified the same way.

## Current deployment mode

**Backend: live on Railway** (`https://pulseiq-production-0585.up.railway.app`,
verified via `GET /api/v1/health` → `200`). **Frontend: not yet deployed**
— still run via Docker Compose or natively for now. **Database:** Neon,
unchanged. **Storage:** local disk (see limitation below).

## Chosen deployment target

| Piece | Platform | Why |
|---|---|---|
| Backend (FastAPI) | **Railway** | Deploys straight from `backend/Dockerfile`; dashboard-driven GitHub integration (push → auto-deploy, no CLI/token needed); supports persistent volumes if local storage ever needs to survive redeploys. |
| Frontend (static Vite build) | **Railway** (second service, same repo) | Originally planned for Vercel; moved to Railway as a second service so both pieces live in one place. Runs the same `frontend/Dockerfile` (build → nginx) standalone, which required fixing two real bugs that only surface outside Docker Compose's own network — see below. |
| Database | **Neon** (already in use) | No change — same Postgres this project has run against natively and via Docker throughout development. |
| Storage | **Local disk** (accepted limitation) | See `docs/STORAGE.md` — uploaded datasets may not survive a Railway redeploy. R2 remains a documented, ready-to-enable upgrade path whenever credentials are available. |

Both services deploy from the same GitHub repo (`Aakif9866/PULSEIQ`) as
two separate Railway services, each with its own **Root Directory**
(`backend` / `frontend`) — Railway's own mechanism for a monorepo with
more than one deployable piece.

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
(not left for Railway to discover) — full writeup in `docs/BUGS.md`
(BUG-001-adjacent Dockerfile fixes):

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

### Setup steps (dashboard/CLI — do this part yourself)

1. Railway → New Project → **Deploy from GitHub repo** → select
   `Aakif9866/PULSEIQ`. Railway will likely try to build from the repo
   root immediately and fail — that's expected on a monorepo with no
   Dockerfile at the root; fix it in the next step rather than starting
   over.
2. In the service's **Settings**, find where it shows the connected repo
   (labeled differently across Railway UI versions — "Source", "Source
   Repo", or just the repo name with an edit icon) → set **Root
   Directory** to `backend`, **Builder** to `Dockerfile`, and
   **Dockerfile Path** to `Dockerfile` — **not** `backend/Dockerfile`.
   This is a real gotcha found and fixed while deploying (BUG-012 in
   `docs/BUGS.md`): once Root Directory is `backend`, the Dockerfile path
   is resolved *relative to that root*, not the repo root — setting it to
   `backend/Dockerfile` makes Railway look for a nonexistent
   `backend/backend/Dockerfile`, which silently falls back to Railpack's
   Python auto-detection (`No start command detected`) instead of an
   obvious error. Redeploy if the change doesn't take effect
   automatically.
3. Add these environment variables (Variables tab):

   | Variable | Value |
   |---|---|
   | `DATABASE_URL` | Your Neon connection string (same one already in local `.env`) |
   | `ENVIRONMENT` | `production` |
   | `DEBUG` | `false` |
   | `SECRET_KEY` | A real, unique secret — **not** the local placeholder. Generate one: `python3 -c "import secrets; print(secrets.token_hex(32))"` |
   | `STORAGE_PROVIDER` | `local` |
   | `MAX_UPLOAD_SIZE_MB` | `200` |
   | `AI_PROVIDER` | `groq` |
   | `GROQ_API_KEY` | Your real key (same one already in local `.env`) |
   | `GROQ_MODEL` | `openai/gpt-oss-120b` |
   | `CORS_ORIGINS` | `["https://<your-frontend-service>.up.railway.app"]` — fill in once the frontend service (below) gives you its real URL; a placeholder here until then just means CORS blocks the frontend, not a security hole |

   Do **not** set `PORT` — Railway injects it automatically.
4. Deploy. Railway gives you a URL — the live backend is currently at
   `https://pulseiq-production-0585.up.railway.app`; copy your own
   service's URL, it's needed for the frontend service.
5. Confirm it's alive: `curl https://<your-railway-backend-url>/api/v1/health`
   should return `{"status":"ok","storage_provider":"local"}`. **Verified
   against the real deployment**: `curl
   https://pulseiq-production-0585.up.railway.app/api/v1/health` returned
   `200` with exactly that body.

### Stray project (deleted)

An earlier round of "New Project from GitHub repo" attempts (while first
figuring out Railway's UI) had left a second, unrelated Railway project
(`joyful-quietude`) with its own `PULSEIQ` service pointed at the same
repo, no root directory configured, failing the same way the main
service used to. It was not part of this deployment plan (one project,
two services), so it was deleted (account owner's choice, via `railway
api`'s `projectDelete`) rather than fixed — confirmed gone from `railway
project list`.

## Frontend on Railway (second service)

The frontend's `frontend/Dockerfile` builds the Vite app then serves it
via nginx — the same image `docker-compose.yml` has always used. Getting
it to run as its *own* standalone Railway service (rather than always
alongside the backend inside Compose's private network) surfaced three
real bugs, all found and fixed by actually running it standalone before
touching Railway, not discovered live on the platform — full detail in
`docs/BUGS.md` (BUG-009, BUG-010, BUG-011):

- nginx **refused to even start** outside Compose — its `/api/` proxy
  rule resolved the hostname `backend` at config-load time, which only
  exists inside Compose's own network. Fixed with a lazy, request-time
  DNS resolver instead.
- The first fix for that introduced a **second** bug: a duplicated
  `/api/` segment in the proxied path, 404-ing every single API call
  through the proxy. Fixed by correcting how the proxy target is written
  once a variable (needed for the lazy resolution above) is involved.
- The container was **hardcoded to port 80** and had **no way to receive
  `VITE_API_URL`** at all — both invisible under Compose, both fatal for
  a standalone/split-host deployment. Fixed: `$PORT` support via nginx's
  own template+envsubst mechanism, and a Docker build `ARG` for
  `VITE_API_URL`.

All three verified directly: `docker run` standalone (no Compose) starts
and serves correctly; a real signup/login round-tripped through the
proxy; `docker build --build-arg VITE_API_URL=...` produces a bundle that
actually contains the given URL (grepped for it in the built JS, not
assumed).

### Setup steps (dashboard/CLI — do this part yourself)

1. In the same Railway project: **New Service** → **GitHub Repo** →
   `Aakif9866/PULSEIQ` again (a second service, separate from the
   backend one).
2. Settings → **Root Directory**: `frontend`. Railway should find
   `frontend/Dockerfile`.
3. Add a **build-time** variable: `VITE_API_URL` =
   `https://<your-railway-backend-url>/api/v1` (from the backend step,
   with `/api/v1` appended — the same path prefix `API_V1_PREFIX` uses
   everywhere else).
   **Verify Railway actually passes this as a Docker build `ARG`**, not
   only a runtime env var — Dockerfile-based builds don't automatically
   get dashboard variables at build time on every platform. Check
   Railway's own docs for "build arguments" / `ARG` referencing if unsure,
   and confirm after deploying by viewing the site's network requests (or
   its built JS under `/assets/*.js`) and checking API calls go to the
   real backend URL, not a relative `/api/v1` path.
4. Deploy. Railway gives you a URL like
   `https://pulseiq-frontend-production.up.railway.app`.
5. **Go back to the backend service** and set `CORS_ORIGINS` to include
   this real URL, e.g. `["https://pulseiq-frontend-production.up.railway.app"]`
   — the backend's default (`localhost` only) will otherwise block every
   request from the deployed frontend with a CORS error, not a helpful
   one.

## Local storage limitation

Covered in full in `docs/STORAGE.md` — the short version: Railway's
filesystem is ephemeral across redeploys unless a persistent volume is
attached. **Uploaded datasets will not survive a redeploy** in this
configuration — accepted as a known limitation for now, not an oversight.
Two ways to change that later, neither requiring a code change: attach a
Railway volume mounted at `LOCAL_STORAGE_ROOT`, or switch
`STORAGE_PROVIDER` to `r2` once Cloudflare credentials are available.

## Database requirements

Unchanged from before — any real Postgres works; this project has run
against a local Homebrew-installed Postgres 16 and a live Neon instance
with no code differences. Migrations (`backend/alembic/versions/`) are
the only schema-management mechanism.

## Verified vs. not yet verified

**Verified on the real platform**, not just simulated locally:
- The backend service (`PULSEIQ`, project `PulseIQ`) actually builds from
  `backend/Dockerfile` on Railway (`build.builder = "DOCKERFILE"`,
  `build.dockerfilePath = "Dockerfile"` relative to `rootDirectory =
  "backend"`) — confirmed via that deployment's own build logs, not just
  the pending config.
- The deployment reached a terminal `SUCCESS` status (polled via
  `railway deployment list --json`, not assumed from a queued/building
  state).
- `curl https://pulseiq-production-0585.up.railway.app/api/v1/health`
  returned `200` with body `{"status":"ok","storage_provider":"local"}` —
  a real HTTP request against Railway's actual infrastructure.
- All environment variables (`DATABASE_URL` pointing at the real Neon
  instance, `SECRET_KEY`, `GROQ_API_KEY`, etc.) are live on that service.

**Verified locally**, standing in for the real platform as closely as
possible:
- The exact Railway frontend runtime contract — standalone `docker run`
  with a dynamic `$PORT` and a `--build-arg VITE_API_URL`, matching what
  a Railway service actually does (mechanism, not the platform itself —
  no frontend Railway service exists yet).
- `docker-compose.yml` still works identically after every fix above
  (regression-checked repeatedly: both containers build and report
  `healthy`, a real signup+login round-tripped through the containerized
  nginx proxy, same as before every change).
- Backend lint (`ruff`), typecheck (`mypy`), and the full test suite
  (48/48 passing) all re-run clean locally after this deployment fix;
  frontend lint (`oxlint`), typecheck (`tsc`), and production build all
  clean too. No application code changed — this was a Railway service
  configuration fix only.

**Not yet verified** (genuinely, not hidden):
- The frontend service does not exist on Railway yet — its setup steps
  above remain a documented plan.
- Whether Railway's dashboard actually passes a declared variable through
  as a Docker build `ARG` for a Dockerfile-based service (the app-level
  mechanism is correct and tested; Railway's specific UI behavior for
  this isn't something confirmed yet since the frontend service hasn't
  been created).
- The real cross-origin request from a deployed frontend to the deployed
  backend on Railway's actual network (the CORS configuration is correct
  by inspection of `app/core/config.py`'s `CORS_ORIGINS` handling, and
  `CORS_ORIGINS` on the live backend is still a `localhost` placeholder
  pending the frontend's real URL).
- Railway's actual ephemeral-storage behavior across a real redeploy of
  the backend (documented as expected behavior for this class of
  platform, not yet observed directly on this deployment across a second
  redeploy).
- (Resolved) The stray `joyful-quietude` Railway project has been
  deleted — see "Stray project (deleted)" above.
