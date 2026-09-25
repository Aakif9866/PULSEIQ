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
| 7 — V2: Hybrid AI Analyst, History & Data Quality | 🟡 Backend done (feature branch); not frontend-wired |
| 8 — V2 Completion & Portfolio Readiness | 🟡 In progress — Steps 1, 2, 4, 5 done; Step 3 built, full run pending quota |

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

## 2026-09-25 (Phase 8 plan captured — nothing executed yet)

- No code changed today. Recorded an incoming 7-step plan (plus one
  optional, ask-first item) as **Phase 8** in
  [PHASES.md](PHASES.md#phase-8--v2-completion--portfolio-readiness):
  wire `/analyze` into the frontend (replacing the still-unvalidated
  `/ask` path the UI currently uses), an NL-to-SQL safety audit, an
  evaluation harness with ground-truth answers, LLM rate-limit/cost
  controls, observability, deployment, and portfolio packaging
  (README rewrite + `docs/RESUME.md`).
- Also recorded **Phase 7** in PHASES.md for the first time — the hybrid
  AI Analyst engine, query history, NL-to-SQL, SQL Explorer, and data
  quality profiling built on `feature/pulseiq-v2-roadmap` in prior
  sessions (commits `aeeed6a`, `b6553ed`) were never entered into this
  tracker before now; this just makes the existing state visible here,
  it doesn't change anything in the code.
- **Next up:** Phase 8, Step 1 — switch the AI Analysis page from `/ask`
  to `/analyze` and surface the validator's evidence in the UI.

## 2026-09-25 (later — Phase 8, Step 1 done)

- **AI Analysis page now calls `/analyze` by default**, not `/ask`. Split
  `ai-analyst-page.tsx` into `AnalyzeAnalystView` (new) and
  `AskAnalystView` (the old page, moved verbatim, unchanged behavior),
  switched by `getAiAnalystEngine()` (`lib/feature-flags.ts`,
  `VITE_AI_ANALYST_ENGINE`, default `"analyze"`). `/ask` stays fully
  reachable and working behind the flag.
- **Evidence panel**: the new view renders which tools ran (as chips,
  failed ones flagged red), a findings list with a verified/unverified
  icon per finding (never hidden when unverified — the whole point of
  the backend's answer validator), a `degraded`-status banner, a
  `needs_clarification` prompt, and any `warnings`.
- **Frontend test infrastructure added from scratch** — this repo had
  zero frontend tests before today. Vitest + `@testing-library/react` +
  jsdom, `npm run test`. Found and fixed a real gap while writing the
  first test: `@testing-library/react`'s auto-cleanup between tests
  depends on detecting a global `afterEach`, which never fires because
  `vitest.config.ts` deliberately runs without `test.globals: true` (kept
  separate from `vite.config.ts` so the Tailwind plugin never runs under
  the test runner) — without an explicit `afterEach(cleanup)` in
  `src/test/setup.ts`, every test after the first rendered on top of the
  previous test's still-mounted DOM. 12 new frontend tests, all passing;
  `npm run typecheck`, `npm run lint`, and `npm run build` all still
  clean.
- **Backend**: 2 new regression tests proving a tool-call error and a
  `degraded` status both survive real HTTP JSON serialization end to end
  — the new frontend code reads `tool_calls[].result.error` and
  `status === "degraded"` directly off the response, so this is the
  actual contract it depends on, not just the in-process Python object.
  227/227 backend tests passing, ruff/mypy clean.
- **Docs**: `docs/AI_ANALYTICS.md` was a bigger gap than expected once
  looked at closely — it described only the old `/ask` pipeline and
  flatly claimed "there is no DuckDB and no generated SQL anywhere in
  this codebase," which stopped being true the moment V2's NL-to-SQL
  landed and was never corrected. Rewritten to cover all three AI paths
  (`/analyze` current default, `/ask` deprecated, NL-to-SQL/SQL Explorer
  provisional pending Phase 8 step 2's security audit), with an explicit,
  honest note that `/analyze`'s system prompt hasn't had the same live
  adversarial testing pass `/ask`'s did.
- **Known, deliberate gap**: "Save insight"/"Add to dashboard" aren't
  wired up for `/analyze` yet (see PHASES.md Phase 8, step 1 for why —
  a schema mismatch, not an oversight).
- **Not done**: no live browser click-through of the new page this round
  (no browser-automation tool available in this environment) — verified
  via component tests (mocked network boundary) and the backend's real
  HTTP contract instead. Worth a manual click-through before calling this
  fully shipped.
- **Next up:** Phase 8, Step 2 — NL-to-SQL safety audit.

## 2026-09-25 (later still — Phase 8, Step 2 done: 2 real bypasses found & fixed)

- **Audited `app/analytics/sql_validator.py`/`sql_engine.py` by actually
  attacking them** — a real Python script throwing real payloads at
  `validate_and_prepare()`/`execute_sql()`, not a code read. Found two
  genuine, working bypasses:
  1. **Bare function calls were never validated.** Only `exp.Table` and
     `exp.Column` nodes were checked — `SELECT version() FROM dataset`
     and `SELECT current_database() FROM dataset` both passed validation
     and DuckDB actually executed them, returning the real engine version
     and in-memory DB name. `SELECT current_setting('data_directory')`
     also passed validation (execution itself happened to fail on that
     particular key). Fixed by rejecting `exp.Anonymous` nodes outright —
     discovered that sqlglot maps every standard SQL function (`SUM`,
     `LOWER`, `CASE`, ...) to its own named class and falls back to
     `Anonymous` for anything else, which covered every non-standard
     function tried (`version`, `current_database`, `current_setting`,
     `read_text`) with no hand-written allowlist needed. Verified
     standard functions (aggregates, `UPPER`, `ROUND`, `CASE`,
     `COALESCE`) still work after the fix.
  2. **A query's own `LIMIT` was never clamped**, only injected when
     absent — `SELECT * FROM dataset LIMIT 999999999` sailed through
     unchanged despite a `row_limit=100` argument. Fixed to always clamp
     to `min(requested, row_limit)`, and to treat a non-literal `LIMIT`
     expression (`LIMIT 1+1`) as unbounded rather than trusted.
  3. Added `enable_external_access=false` on the DuckDB connection as a
     second, independent layer — verified live it doesn't break the
     registered dataset table, but does independently block
     `read_csv('/etc/passwd')`/`INSTALL` even calling `execute_sql()`
     directly with unvalidated SQL.
  4. Closed a real test-coverage gap along the way: `QUERY_TIMEOUT_SECONDS`
     had never actually been exercised by a test for the SQL path in this
     whole codebase — added one (mocked a slow `execute_sql`, confirmed a
     clean `408` within the configured window, not a hang).
  5. Added a real cross-user ownership test for `/ask-sql`
     (`test_ask_sql_cannot_reach_another_users_real_dataset`) — the only
     prior test used a nonexistent UUID, which would pass even if
     ownership scoping were completely broken.
- **18 new backend tests, 245/245 passing**, ruff/mypy clean.
- **Docs**: found and fixed the *same* stale, false claim
  ("there is no SQL/DuckDB anywhere in this codebase") in **both**
  `docs/ARCHITECTURE.md` and `docs/SECURITY.md` — both predated V2's
  NL-to-SQL and were never corrected after it shipped, in addition to
  `docs/AI_ANALYTICS.md` from Step 1. `docs/SECURITY.md` now has a full,
  itemized "Natural Language to SQL / SQL Explorer — audited" section
  covering every guarantee and exactly what was tried against it.
- **What the audit did not find** (stated honestly, not implied): no
  exploit reading an arbitrary file, reaching the network, or crossing
  into another user's data — both real findings were information
  disclosure limited to the querying user's own request/response. That
  doesn't rule either out, only that these specific attempts didn't find
  one.
- **Next up:** Phase 8, Step 3 — evaluation harness.

## 2026-09-25 (later still — Phase 8, Step 3 built, live run partially complete)

- **Built `evals/`**: 51 questions across 2 deterministically-generated
  sample datasets (e-commerce, employees — both with deliberately
  injected duplicates, missing values, out-of-range values, and a
  formula mismatch), covering all 16 tools, NL-to-SQL, and 4 multi-step
  questions. Ground truth computed by calling `app.ai.tools` directly
  (never the LLM). A runner that drives each question through the real,
  live Groq-backed pipeline and scores tool-selection accuracy, value
  accuracy, and the validator's intervention rate, with real token/
  latency numbers captured via an external instrumentation layer
  (`evals/instrumentation.py`) that patches the one shared Groq client —
  zero changes to any file under `backend/app/` needed for that part.
- **Found and fixed BUG-016 within the first 5 questions of the first
  live run**: the model called `get_duplicates` with `{"column": null}`
  (normal tool-calling behavior for "omit this"), and Groq's own schema
  validation rejected it outright — 400 on all 3 retries, failing the
  whole question. Root cause: every optional tool parameter in
  `app/ai/tool_specs.py` was a bare `{"type": "string"}` with no `null`
  allowed. Fixed by auto-widening every non-required property's schema
  to accept `null`, verified live against the real Groq API before
  rolling it out, plus stripping `None`-valued arguments in `call_tool()`
  so an explicit null and an omitted key behave identically. 5 new
  backend tests, 250/250 passing.
- **Relaunched the full run — got 26/51 questions through with a real,
  successful answer before hitting a second, harder constraint**: Groq's
  free tier caps total tokens *per day* (200,000 TPD), not just per
  minute — question 27 hit it directly (`Used 199747, Requested 1057`).
  This is a genuine external resource limit, not a bug — exactly what
  Phase 8 step 4 exists to manage (quotas, a fallback provider, cost
  visibility).
- **A real mistake, caught and fixed, not hidden**: killed the process
  once it was clear continuing would just spend the rest of a ~20-minute
  retry window on near-certain 429s — but `runner.py` only wrote its
  results file at the very end of a full run, so the detailed
  per-question data (answers, scores, tokens) for all 26 successful
  questions was lost, leaving only the coarse pass/fail lines already
  printed to the console log. **Fixed**: results are now written after
  every single question, and a new `--resume` flag skips whatever
  already succeeded rather than re-spending quota re-running it. 2 new
  tests for this (`evals/test_runner.py`, run via plain `pytest`, not
  part of the backend suite since `evals/` isn't application code).
- **`docs/EVALS.md`** records this status honestly — a "what happened"
  section instead of a results table filled with estimated numbers.
  Genuinely verified without needing the lost data: the full pipeline
  works end-to-end against a real live model (26/27 attempted questions
  succeeded with sane answers, observed directly), and one real,
  interesting finding survived in the log either way — a `Finding` whose
  `value` came back as a list of row dicts instead of a scalar was
  caught and dropped cleanly by existing validation
  (`analysis_finding_dropped_invalid_shape`) rather than crashing.
- **Next up:** resume the run (`--resume`) once Groq's daily quota has
  enough headroom — the retry-after values observed (5-19 minutes,
  fluctuating) suggest a rolling window rather than a fixed daily reset,
  so this may be resumable later today rather than only tomorrow. Once
  it completes, fill in `docs/EVALS.md`'s results table with the real
  numbers and mark Phase 8 step 3 fully done. Then step 4.

## 2026-09-25 (evening — eval resume attempt; Phase 8, Step 4 done)

- **Eval resume attempt:** waited 20 minutes and resumed with `--resume`.
  Groq's daily cap had barely recovered (~2,100 tokens freed in ~27
  minutes), and every remaining question failed with a 429 — 0/51
  succeeded in that run. The new backoff cap worked as intended: each
  question gave up in ~15s instead of hanging for the 7-18 minutes Groq
  suggested. That results file held only quota failures, so it was
  deleted rather than kept where it could be mistaken for eval data. The
  full run is deferred until the daily quota resets.
- **Resource-ownership check** (asked for before the migration): the
  GitHub remote is the personal `github-personal:Aakif9866` alias, the
  account email is a personal Gmail matching that handle, the Neon
  project uses Neon's auto-generated defaults with no company branding,
  R2 isn't configured at all, and nothing points to an employer's
  account. Dashboards themselves weren't checked (no login access). **A
  mistake in the process:** a redaction command assumed the wrong URL
  scheme and printed the Neon database password to the session output.
  Flagged immediately; the password should be rotated.
- **Step 4 audit first, as the plan asked:** the model already never saw
  raw data — only column names/dtypes up front, tool results truncated
  at 4,000 chars, history capped at 5 turns, the loop at 6 iterations.
  Found one wrong claim in `docs/AI_ANALYTICS.md`: it said 429s were
  "handled with retry/backoff". They weren't — retries fired instantly.
- **Added:** backoff with full jitter honoring Groq's own suggested wait
  (Retry-After header, or its error text when the header's missing),
  capped at 8s; an in-process answer cache keyed by (dataset_id,
  normalized question), fresh questions and "ok" answers only; a
  `UsageTrackingProvider` wrapper that totals Groq-reported tokens and
  latency across the tool loop without touching `run_analysis` or the
  response schema; config-driven cost (unset = "Not tracked", never
  $0.00); migration 0009 (`ai_usage_log`, verified upgrade → downgrade →
  upgrade on a throwaway database); opt-in per-user daily token quotas
  (UTC midnight reset, 429 with the reset time, cached answers still
  served, delete-and-re-upload can't reset it); `GET /usage/me` and a
  Usage page; a `FallbackProvider` mechanism, tested but not wired (no
  second real provider exists).
- **Not done, stated in the docs:** model tiering, token counting for
  `/ask`/`/ask-sql` (they bypass the provider abstraction but are still
  quota-blocked), an all-users admin view (no admin role), and a real
  before/after token measurement (blocked on the quota — the n=3 spot
  measurements that exist are recorded in `AI_ANALYTICS.md`, labeled
  as a spot check).
- **Tests:** 42 new backend tests (292/292), 7 new frontend tests
  (19/19); ruff, mypy, typecheck, lint, and build all clean.
- **Next up:** Phase 8, Step 5 — observability and reliability.

## 2026-09-25 (night — Phase 8, Step 5 done)

- **Checked what existed first.** Per-request `request_id` binding and an
  `X-Request-ID` echo already existed (Phase 6). Then verified the claims
  instead of trusting them, and found three real gaps:
  1. An inbound `X-Request-ID` was ignored, so there was no shared id
     between a browser error and its server log lines.
  2. An unhandled 500 carried no `X-Request-ID`, and the log line holding
     the actual error carried no `request_id` either (BUG-018). The
     exception escaped the middleware to Starlette's outermost handler,
     which logs after the request's context is already cleared.
  3. `ThreadPoolExecutor.submit()` doesn't copy contextvars: confirmed
     with a direct probe (`{}` inside the worker). Nothing logs inside
     those workers today, but any span or log line added there later
     would silently lose its request.
- **Fixed all three:** inbound ids honored when well-formed (validated,
  so newline-injection-shaped or oversized ids are replaced); the
  middleware now builds the 500 itself while the context is bound (same
  generic body, plus the id); `submit_in_context()` used at all three
  submit sites; CORS `expose_headers` so the deployed frontend on another
  origin can actually read the id.
- **Frontend:** every request sends a fresh id (with a
  `getRandomValues` fallback for plain-http contexts where
  `crypto.randomUUID` doesn't exist); `ApiError` carries the server's
  echoed id; errors show it as a quotable "Reference".
- **Tool and LLM log lines:** `tool_call_completed` and
  `llm_call_completed` (tokens and timing, never message content), both
  inheriting the request's id.
- **Optional OpenTelemetry tracing**, off unless
  `OTEL_EXPORTER_OTLP_ENDPOINT` is set. Read through Settings rather than
  `os.environ`, since pydantic-settings never puts `.env` values into
  `os.environ` and the exporter would otherwise silently never see it.
- **Live verification:** ran a small OTLP receiver that decodes the real
  protobuf export, started the real backend pointed at it, and sent one
  request with `X-Request-ID: live-e2e-1`. Result: the id echoed, every
  log line carried it plus one shared `trace_id`, and the receiver got
  the matching trace (HTTP → analyze → llm.chat). **It also exposed
  BUG-017:** Groq's quota was still exhausted, and `/analyze` answered
  `400 "The request could not be completed."`, because only the final
  LLM call was guarded and a failure on the first (tool-loop) call
  escaped the engine. Fixed; the new tests fail with the fix reverted
  and pass with it restored; re-verified live as a degraded 200.
- **Max-iterations test rewritten:** the old one scripted exactly 6 tool
  rounds and then an answer, so the *model* stopped by itself; it would
  have passed with no cap at all. The new one uses a model that never
  stops asking for tools.
- **Tests:** 309/309 backend (17 new), 24/24 frontend (5 new); ruff,
  mypy, typecheck, lint, build clean. Also stubbed out real backoff
  sleeps in the provider tests (one test there was spending 0.67s
  genuinely asleep; the whole file now runs in 0.10s).
- **Next up:** Phase 8, Step 6 — ship it.

## 2026-09-25 (late night — Phase 8, Step 6 in progress)

- **Decisions asked for and made by the account owner:** PR first,
  merge once CI is green; stay on local-disk storage (R2 needs a
  Cloudflare payment method on file); per-user AI quota of 30,000
  tokens/day; a freshly generated public demo password.
- **Demo seeder** (`app/workers/seed_demo.py`), run at every container
  start. Idempotent, and it self-repairs the local-disk failure mode
  where a redeploy wipes files but keeps their rows. 7 tests against
  the real DB and storage. **Verified inside the real backend image**
  (`docker build` plus a run against a DB whose demo files didn't exist
  in the fresh container): it removed the broken dataset, re-uploaded,
  re-added the chart, then the server started and `/health` returned
  200 with the request id echoed.
- **CI:** frontend tests added; a new evals job (harness tests,
  byte-for-byte dataset determinism, ground truth for all 51 questions,
  demo dataset matches eval dataset); a new Docker job building both
  images; a separate manual live-evals workflow, so model quota is never
  spent per push. Every new step was run locally, verbatim; GitHub
  hasn't run them yet.
- **Ownership, settled for Railway:** the project is in the workspace
  "aakif9866's Projects", personal and matching the GitHub handle.
- **Next:** you open the PR; once CI is green, set the three production
  variables, merge, and verify the live deploy for real.

- **Step 7 drafted while the PR is pending:** README and `docs/RESUME.md`
  written, then audited against the code. Three overstatements in the
  first draft were corrected before committing (tool engine, validator
  scope, which bug came from tracing). Resume bullets checked by script:
  21-24 words, verb-first, no pronouns. Outstanding: a GIF (needs a human
  screen recording) and eval accuracy (needs a complete live run).
