# Progress Log

Status tracker for [PHASES.md](PHASES.md). Newest entry on top. Keep entries
short — what changed and what's next, not a full diff.

## Status at a glance

| Phase                              | Status         |
| ----------------------------------- | -------------- |
| 1 — Foundation & Auth               | ✅ Done         |
| 2 — Dataset Upload & Storage        | ✅ Done (profiling moved to Phase 3) |
| 3 — Analytics Engine                | ✅ Done         |
| 4 — AI Analyst (Groq)               | ✅ Done         |
| 5 — Dashboards & Visualization      | ✅ Done         |
| 6 — Hardening & Deployment          | 🟡 Partial (see Deferred in PHASES.md) |

## Known issues

- ~~**Docker Desktop build environment**~~ — **RESOLVED**. A clean
  `pkill` + relaunch of Docker Desktop cleared the wedged daemon; the
  build then succeeded (BuildKit's cache had actually retained the heavy
  `pip install` layer from the original failed attempt, so it didn't need
  to redo that work). `docker compose up` now brings up backend + frontend
  cleanly, both reporting `healthy`. See BUGS.md BUG-005 for a real bug
  found in the process (frontend's own HEALTHCHECK always failed due to
  an IPv4/IPv6 loopback mismatch — fixed). **Worth remembering:** this
  machine has only 8GB total RAM, and Docker's VM was already configured
  for 4096MiB (half the machine) when it originally OOM'd — raising that
  further would leave very little for macOS itself, so that was
  deliberately *not* done; the fix was restarting the wedged daemon, not
  giving it more memory.

## 2026-09-05

- Repo initialized: FastAPI backend + React/Vite frontend + Docker Compose
  (Postgres, backend, frontend/nginx), scaffolded and committed to disk
  (not yet committed to git — `master` has no commits yet).
- Phase 1 complete in code: JWT auth (signup/login/refresh/me), User model +
  Alembic migration, health check, structured logging, centralized
  exception handling; frontend shell with landing/login/signup pages,
  protected routes, and a workspace layout whose nav items (Datasets,
  Dashboards, AI Analyst, Insights, Settings) are placeholders pending
  their phases.
- Backend test suite (pytest) covers health check and the auth flow
  (signup, duplicate email, bad password, unauthenticated `/me`).
- Added `PHASES.md`, `PROGRESS.md`, and root `README.md`.
- **Phase 2 backend slice implemented:** `Dataset` model + Alembic
  migration (`0002_create_datasets`), a `StorageProvider` abstraction
  (`app/storage`) with `local` filesystem and R2 (boto3, S3-compatible)
  implementations selected via `STORAGE_PROVIDER`, `DatasetRepository` /
  `DatasetService`, and `POST/GET /api/v1/datasets` +
  `GET /api/v1/datasets/{id}` (extension/size validation, ownership-scoped,
  404 on another user's dataset). 6 new pytest cases added.
- Validated the above for real: since Docker is still down, installed
  Postgres 16 natively via Homebrew (`brew install postgresql@16`),
  started it temporarily, ran `alembic upgrade head` (both migrations
  apply cleanly) and the full suite — **11/11 tests pass**. Also confirmed
  `ruff`/`mypy` are clean on all new files (both tools flag a handful of
  pre-existing issues in files this change didn't touch —
  `alembic/env.py`, `0001_create_users.py`, `app/main.py`,
  `tests/test_auth.py`, `app/core/logging.py` — left alone as out of
  scope). Stopped the temporary Postgres afterward; the Homebrew install
  and the local `.venv` are left in place as a working native dev setup
  (see README Option B). Restart it with:
  `PATH="/opt/homebrew/opt/postgresql@16/bin:$PATH" pg_ctl -D /opt/homebrew/var/postgresql@16 -l /tmp/pg16.log start`
  — the `pulseiq` role/database already exist.
- **Phase 2 frontend slice implemented:** `/workspace/datasets` now a real
  page (`datasets-page.tsx`) instead of the placeholder — upload button
  (hidden file input, `.csv/.xlsx/.xls`), dataset list with size/status/
  uploaded-date, loading/error/empty states. Added `apiClient.upload()`
  (FormData, skips JSON-encoding so the browser sets the multipart
  boundary), `features/datasets/api.ts` (`useDatasets`, `useUploadDataset`
  via TanStack Query, invalidates the list on success), `types/dataset.ts`,
  and `formatBytes`/`formatDate` helpers in `lib/utils.ts`. Also wired the
  workspace home page's dataset count and "Recent datasets" card to real
  data instead of hardcoded zeros.
- Validated end-to-end for real, not just typecheck/lint: started the
  native Postgres + backend + `vite dev`, and drove the exact HTTP calls
  the frontend makes (`curl -F file=@...`) through both the backend
  directly and through Vite's `/api` dev proxy — signup → upload → list
  all matched the `Dataset` shape the new frontend code expects, and the
  415 case (unsupported extension) round-tripped correctly. `tsc -b
  --noEmit` and `oxlint` both clean. Shut everything down afterward
  (`pkill` vite/uvicorn, `pg_ctl stop`) — nothing left running.
- **Phase 3 (Analytics Engine) implemented, backend + frontend:**
  - Backend: `app/analytics/` (`loader.py`, `profiling.py`,
    `query_engine.py`, all Polars-based), migration `0003` adds
    `row_count`/`column_count`/`columns_profile` (JSONB) to `datasets`.
    Profiling runs synchronously right after upload and
    degrades gracefully (`status="profiling_failed"`) rather than failing
    the upload if the file can't be read (e.g. legacy `.xls`, corrupt
    CSV). New `POST /api/v1/datasets/{id}/query` accepts a structured
    group_by/aggregations/filters/sort/limit body (no raw SQL — the
    frontend builds this from dropdowns) and enforces `QUERY_ROW_LIMIT`
    always, plus a `QUERY_TIMEOUT_SECONDS` HTTP-level guard via a
    thread-pool future (documented as not a true compute-cancelling kill
    switch — that needs an out-of-process worker, Phase 6). 6 new pytest
    cases in `test_dataset_query.py`; updated one pre-existing assertion
    in `test_datasets.py` that predated profiling.
  - Fixed the local dev environment along the way: the `.venv` had been
    created against whatever Python happened to be active (3.10, via
    pyenv), not the project's actual target (3.12, per `pyproject.toml`
    and the Dockerfile) — this surfaced when a routine `ruff --fix`
    correctly modernized `datetime.now(timezone.utc)` to `datetime.now(UTC)`
    (valid Python 3.11+) and broke on 3.10. Rebuilt `.venv` against
    `/Library/Frameworks/Python.framework/Versions/3.12` so local dev
    actually matches what ships.
  - Frontend: `/workspace/datasets/:id` is now a real explorer page —
    column stats table, a raw-rows/summary mode toggle, one filter row,
    results table with a truncation notice. New `Select` UI primitive
    (matches `Input`'s styling), `useDataset`/`useRunDatasetQuery` hooks,
    dataset list rows now link into the explorer.
  - Validated end-to-end again: native Postgres + backend + `vite dev`,
    drove signup → upload → detail (profile fields populate) → query
    (`group_by=["region"], sum(amount)`) through Vite's `/api` proxy —
    exact shape the frontend code expects. `tsc -b --noEmit`, `oxlint`,
    `ruff`, `mypy` all clean (mypy's one finding is the same pre-existing
    `app/core/logging.py` issue noted in Phase 2, still untouched).
    17/17 backend tests pass. Shut everything down afterward.
- **Phase 4 (AI Analyst / Groq) implemented, backend + frontend, and
  validated against the real Groq API (user supplied `GROQ_API_KEY` in
  `.env`, flipped `AI_PROVIDER` from `none` to `groq`):**
  - **Found and fixed a stale default**: `GROQ_MODEL` defaulted to
    `llama-3.3-70b-versatile`, which Groq has since retired — the real
    API call 404'd with `model_not_found`. Queried `client.models.list()`
    with the user's key to see what's actually available now and switched
    the default (`.env`, `.env.example`, `config.py`) to
    `openai/gpt-oss-120b`, confirmed working with JSON mode.
  - Backend: `app/ai/groq_client.py` (SDK wrapper) + `app/ai/analyst.py`
    (two-call design: question+profile → structured `DatasetQueryRequest`
    in JSON mode, executed through Phase 3's existing safe query engine;
    then question+actual result → plain-language answer — deliberately
    not text-to-SQL, so it inherits Phase 3's row cap/timeout for free and
    opens no new injection surface). `insights` table (migration `0004`),
    `InsightRepository`/`InsightService` (re-verifies dataset ownership on
    save since `dataset_id` is client-supplied), `AnalystService` orchestrating
    the ask flow. New routes: `POST /api/v1/datasets/{id}/ask`,
    `POST/GET /api/v1/insights`, `DELETE /api/v1/insights/{id}`.
  - Tightened the answer prompt mid-flight: the first live answer came
    back with markdown bold (`**north**`) that the plain-text UI would
    have shown as literal asterisks — added an explicit "plain text only,
    no markdown" instruction and confirmed the fix with another real call.
  - 6 new pytest cases in `test_ai_analyst.py`, Groq calls mocked
    (`monkeypatch.setattr("app.services.analyst_service.build_query_from_question"/"summarize_result", ...)`)
    so the automated suite stays deterministic/offline — **23/23 pass**.
  - Frontend: `/workspace/ai-analyst` (dataset picker limited to
    `status === "profiled"`, question box, answer + result table, "Save
    insight") and `/workspace/insights` (list with delete) are now real
    pages instead of placeholders. Workspace home's third stat tile is
    now "Insights saved" (real count) instead of a hardcoded "AI analyses
    run" zero — renamed since we only count saved insights, not every
    question asked.
  - Validated end-to-end with the **real** Groq API (not mocked) through
    both the backend directly and Vite's `/api` proxy: a `sum`+`group_by`
    question, a filter-only question, and a `sort+limit` ("lowest total")
    question all produced correct structured queries and answers that
    matched the actual CSV data; saved an insight and listed it back.
    `tsc -b --noEmit`, `oxlint`, `ruff`, `mypy` all clean (mypy's one
    finding is still the pre-existing, untouched `app/core/logging.py`
    issue). Shut everything down afterward (backend, vite, Postgres) —
    nothing left running.
- **Phase 5 (Dashboards & Visualization) implemented, backend + frontend:**
  - Loaded the `dataviz` skill before writing any chart code (it applies to
    inline app code, not just Artifacts). Read `choosing-a-form.md` and
    `anti-patterns.md` first: pie/donut is explicitly flagged as an
    anti-pattern for this kind of comparison data ("Bad: a 2-slice pie /
    donut for comparing close values"), so chart types were narrowed to
    **bar and line only** rather than the originally-planned three.
    Pulled the dark-mode categorical palette from `references/palette.md`
    and validated it against this app's *actual* card surface (`#101114`,
    not the skill's generic default) with
    `node scripts/validate_palette.js ... --mode dark --surface "#101114"`
    — all 8 slots pass lightness/chroma/CVD/contrast. Baked the passing
    hex values into `lib/chart-theme.ts` + `lib/chart-options.ts` (colors
    assigned by fixed slot order, never cycled; single y-axis always;
    legend only shown for 2+ series, matching the skill's rule that a
    lone series needs no legend box).
  - Backend: no new query/analytics logic needed at all — a
    `DashboardChart` is just `{dataset_id, title, chart_type,
    query_request}`; rendering it means re-running that same
    `DatasetQueryRequest` through Phase 3's existing `/datasets/{id}/query`.
    New tables `dashboards` + `dashboard_charts` (migration `0005`,
    ordinal `position` column for arrangement).
    `DashboardRepository`/`DashboardChartRepository`/`DashboardService`,
    routes: `POST/GET /api/v1/dashboards`, `GET/DELETE
    /api/v1/dashboards/{id}`, `POST/DELETE .../charts(/{id})`, `POST
    .../charts/{id}/move`. Ownership of both `dashboard_id` and the
    chart's `dataset_id` (client-supplied) is re-verified server-side,
    same pattern as Insights in Phase 4. 6 new pytest cases — **29/29
    pass**.
  - Frontend: `/workspace/dashboards` (list, create, delete) and
    `/workspace/dashboards/:id` (canvas — chart grid with move/delete)
    replace the placeholder. `AddToDashboardControl` is a single shared
    component wired into both the dataset explorer and the AI analyst
    page, so "add to dashboard" behaves identically from either entry
    point (only shown once a result has 2+ columns — something worth
    actually charting). Workspace home's "Dashboards" tile now shows a
    real count.
  - Validated end-to-end again: `tsc -b --noEmit`, `oxlint`, `ruff`,
    `mypy` all clean (mypy's one finding is still the same pre-existing,
    untouched `app/core/logging.py` issue); a full `npm run build` also
    passes (flags the echarts bundle as a large chunk — a real but
    separate concern, noted below, not fixed here). Then, with native
    Postgres + backend + Vite running, drove the actual flow through
    Vite's `/api` proxy: create dashboard → add a chart with a real
    `group_by`+`sum` query → fetch dashboard detail → re-run the chart's
    stored query (exactly what `ChartCard` does on load) → move → delete
    — every response matched the shape the frontend's types expect.
    Shut everything down afterward.
  - **Noted, not fixed:** `npm run build` warns the JS bundle is ~1.6MB
    (mostly from `echarts`) with no code-splitting configured anywhere
    in the app yet. Not a regression from this phase's scope, but worth
    a route-level lazy-load pass if load time becomes a real complaint.
- **Phase 6 (Hardening & Deployment) — scoped down before starting.**
  Asked which of the two open-ended items to take on: background workers
  and deployment target both got "skip for now" (recommended defaults) —
  logged as deliberate, revisitable deferrals in PHASES.md, not silently
  dropped. Implemented the rest:
  - **CI**: `.github/workflows/ci.yml` — `backend` job (ruff, mypy,
    migrations + pytest against a real Postgres service container) and
    `frontend` job (oxlint, tsc, build), on push to `main` and every PR.
    Validated the YAML parses correctly; commands mirror exactly what's
    been run manually all along (same ruff/mypy/pytest/npm invocations),
    so there's nothing here CI could catch that hasn't already been
    exercised — its value is running it automatically going forward.
  - **Hardening**: `Settings` gained a `model_validator` that refuses to
    even construct when `ENVIRONMENT=production` with the still-default
    `SECRET_KEY` or `DEBUG=true`. Verified live: importing the app with
    `ENVIRONMENT=production` and the default secret raises immediately
    with a clear message, before anything else in the app runs.
  - **Observability**: new `RequestLoggingMiddleware` — binds a
    `request_id` to structlog's contextvars per request (every log line
    anywhere during that request carries it, no plumbing needed) and
    echoes it as `X-Request-ID`. Caught and fixed a real bug in my own
    first draft while writing it: clearing the contextvar in a bare
    `finally` ran *before* the success-path log line, so `request_id`
    would never actually appear on `request_completed` — restructured to
    `try/except/else/finally` so both log lines fire before the clear.
    Verified live (not just by the test): the emitted log line and the
    response header carry the identical id.
  - 6 new pytest cases (`test_config.py`, plus two in `test_health.py` for
    the request-id header) — **34/34 pass**. `ruff`/`mypy` clean (same
    one pre-existing `logging.py` finding as every prior phase).
  - Did not add external error tracking (Sentry or similar) — it needs a
    real account/DSN to be worth wiring up, so it waits alongside
    deployment rather than being stubbed in unused.
- **Next up:** resume the parked Docker Desktop issue, pick a background-
  worker approach and/or deployment target to unblock the deferred parts
  of Phase 6, or start scoping Phase 7 (there wasn't one planned — the
  product roadmap in PHASES.md ends at Phase 6).

## 2026-09-05 (later — full QA pass, then Docker fix)

- **Full QA/hardening pass** requested against the running app (by then
  pointed at a real Neon Postgres instance, `DATABASE_URL` supplied by
  the user). Ran it as a genuine test → document → fix → retest cycle,
  not a code-only review — see **[BUGS.md](BUGS.md)** for the full record.
  5 real bugs found, all fixed and re-verified:
  - **BUG-001 (Critical):** backend couldn't start at all against a
    standard `postgresql://` URL (Neon's own format) — only `psycopg` v3
    is installed, not legacy `psycopg2`. Fixed with a `Settings` validator
    that normalizes the scheme automatically.
  - **BUG-002 (Medium):** CSV columns with leading zeros (zip codes, IDs)
    silently lost them via Polars' default inference — `"007"` became
    `7`. Fixed by disabling inference and re-casting columns myself,
    except any with a leading-zero value.
  - **BUG-003 (High):** asked to "delete all records" or "update revenue
    to zero," the AI **claimed the mutation succeeded** — pure
    hallucination (there's no mutation capability anywhere in the schema;
    data was always untouched, verified). Fixed via an explicit
    instruction in the answer prompt.
  - **BUG-004 (Medium):** no React error boundary anywhere — any
    unhandled render error would white-screen the whole app. Added one.
  - **BUG-005 (Medium, found afterward while fixing Docker):** the
    frontend container's own `HEALTHCHECK` always failed (IPv4/IPv6
    loopback mismatch) even though the container served real traffic
    correctly. Fixed.
  - What genuinely passed with no fixes needed: auth (including forged/
    expired JWTs), cross-tenant isolation across datasets/insights/
    dashboards/charts, injection-style filter values (inert — no SQL
    surface exists to inject into), **direct and data-embedded prompt
    injection** (the AI quoted an injected instruction from a dataset
    cell but refused to follow it), impossible-question hallucination
    resistance, R2 misconfiguration (clean 500, no crash, no leaked
    internals), upload size-limit enforcement (no orphaned records).
  - Honest limitations logged, not hidden: no frontend test suite exists;
    R2 untested against a real bucket (no credentials); one pre-existing
    cosmetic mypy finding in `logging.py` left alone.
- **Docker fixed.** The Docker Desktop VM had been wedged (not just
  slow) since the very first message of this project — `docker info`
  hung even after this session's earlier "known issue" note. A clean
  `pkill -9` of every Docker process + relaunch cleared it immediately.
  `docker compose build` then succeeded for both `backend` and
  `frontend` (BuildKit's cache had retained the expensive `pip install`
  layer from the original failed attempt), and `docker compose up`
  brought up both containers healthy, verified with a real signup/login
  call through the containerized nginx `/api` proxy — not just natively.
  **Noted for the future:** this machine has only 8GB total RAM; Docker's
  VM was already configured for 4096MiB (half the machine) when it
  OOM'd originally, so memory was deliberately *not* raised further —
  the fix was restarting the wedged daemon, not giving it more RAM.
- **`docker-compose.yml` simplified** at the user's request ("Neon is
  fine as a backend, no need to maintain 2 files"): removed the local
  `postgres` service and its volume entirely, and removed the
  `DATABASE_URL` override that had been hardcoding the backend container
  to talk to that now-removed local container. The backend container now
  just inherits `DATABASE_URL` from `.env` via `env_file`, same as native
  runs — one database (Neon) used everywhere, nothing to keep in sync.
  Updated `.env.example` (dropped the now-unused `POSTGRES_USER/
  PASSWORD/DB`, documented the scheme-normalization from BUG-001) and
  `README.md`'s Option A/B instructions to match.
- **Next up:** git init/first commit (still nothing committed to
  `master`), a deployment target if/when wanted, or picking up any of the
  genuine limitations logged in BUGS.md (frontend test suite, real R2
  credentials, etc.).
