# PulseIQ — Phase Plan

PulseIQ is an AI-powered, self-service analytics platform: users upload a
dataset (CSV/Excel), explore it, and ask questions about it in plain language.
This document is the source of truth for scope ordering. Update it whenever a
phase's scope changes; track day-to-day status in [PROGRESS.md](PROGRESS.md)
instead of here.

Each phase should leave the app in a demoable state — no long-lived branches
that leave `main` broken.

---

## Phase 1 — Foundation & Auth

Scaffolding, accounts, and the app shell everything else plugs into.

- [x] Repo scaffolding: FastAPI backend, React (Vite) frontend, Docker Compose
      for local dev (Postgres + backend + frontend)
- [x] Postgres + SQLAlchemy + Alembic migrations
- [x] User model, structured logging, centralized error handling
- [x] JWT auth: signup, login, refresh, `/auth/me`
- [x] Frontend shell: landing page, login/signup pages, protected routes,
      workspace layout with nav (Datasets, Dashboards, AI Analyst, Insights,
      Settings — placeholders for now)
- [x] Backend test suite for health + auth (pytest)

**Exit criteria:** a user can sign up, log in, and land on an empty
workspace shell, end to end, running via `docker compose up`.

## Phase 2 — Dataset Upload & Storage

- [x] File upload endpoint (CSV/XLSX), size + extension validation
      (`MAX_UPLOAD_SIZE_MB`, `ALLOWED_UPLOAD_EXTENSIONS`)
- [x] Storage abstraction: `local` filesystem provider (dev) and Cloudflare R2
      provider (prod), selected via `STORAGE_PROVIDER`
- [x] Dataset metadata model + repository (filename, size, content type,
      owner, upload timestamp, status)
- [ ] Basic profiling on ingest: column names, inferred dtypes, row count,
      null counts — deferred to Phase 3, where DuckDB/Polars/openpyxl land
- [x] Dataset list/detail API (`GET/POST /api/v1/datasets`,
      `GET /api/v1/datasets/{id}`, ownership-scoped)
- [x] Frontend: replace the Datasets placeholder with an upload flow and a
      dataset list (a dedicated detail/profile view is deferred to Phase 3 —
      there's no profiling data yet to justify a separate page)

**Exit criteria:** a logged-in user can upload a CSV, see it listed with
basic metadata (filename, size, upload time), and reopen it later.
Profiling (dtypes, row/null counts) moved to Phase 3 alongside the
DuckDB/Polars engine that computes it.

## Phase 3 — Analytics Engine

- [x] Query engine over uploaded datasets — Polars only for now (DuckDB
      stays a requirements.txt dependency, reserved for when raw
      user-authored SQL is actually needed; the structured group_by/filter
      shape below doesn't need a second engine)
- [x] Query safety: enforced row cap (`QUERY_ROW_LIMIT`, always applied
      regardless of what's requested) and a timeout (`QUERY_TIMEOUT_SECONDS`)
      — bounds the caller's wait via a thread-pool `future.result(timeout=)`;
      note this is an HTTP-level guard, not a true kill switch (Python can't
      forcibly cancel a running native Polars call) — a real one needs an
      out-of-process worker, i.e. Phase 6
- [x] Aggregation/filter/group-by API for a dataset
      (`POST /api/v1/datasets/{id}/query`) — empty `aggregations` = a raw
      filtered/sorted table preview; non-empty = a grouped summary
- [x] Dataset profiling, moved here from Phase 2: row/column count and
      per-column {name, dtype, null_count}, computed synchronously right
      after upload (`DatasetService._profile`) and persisted on the
      `datasets` row (migration `0003`). CSV and .xlsx (via openpyxl)
      supported; legacy .xls is still accepted at upload but marked
      `status="profiling_failed"` — no dependency for reading it yet.
- [x] Dataset explorer UI: `/workspace/datasets/:id` — column stats table,
      a raw-rows/summary toggle (group-by + aggregate, or filter+sort),
      one filter row, results table with a truncation notice

**Exit criteria:** a user can explore a dataset's data and run basic
aggregations through the UI without writing any query themselves.

## Phase 4 — AI Analyst (Groq) ✅

- [x] Groq provider integration behind `AI_PROVIDER` — `app/ai/groq_client.py`
      + `app/ai/analyst.py`. `GROQ_MODEL` default updated to
      `openai/gpt-oss-120b`; `llama-3.3-70b-versatile` (the original
      default) has been retired from Groq's catalog and now 404s.
- [x] Natural-language question → generated query/insight over a dataset —
      deliberately NOT text-to-SQL. Two Groq calls: (1) question + column
      profile → a `DatasetQueryRequest` (JSON mode, Pydantic-validated),
      executed through Phase 3's existing safe query engine (same row cap
      + timeout, no new injection surface); (2) question + the *actual
      computed result* → a plain-language answer, so the model summarizes
      real numbers instead of guessing. `POST /api/v1/datasets/{id}/ask`.
- [x] AI Analyst workspace UI wired up — dataset picker (profiled datasets
      only) + question box + answer/result table + "Save insight".
- [x] Save/retrieve insights — `insights` table (migration `0004`),
      `POST/GET /api/v1/insights`, `DELETE /api/v1/insights/{id}`; Saved
      Insights page lists them with the dataset filename, question,
      answer, and a delete button. Ownership of `dataset_id` is
      re-verified server-side on save (it's client-supplied, round-tripped
      from an `/ask` response).

**Exit criteria:** a user can ask a plain-language question about their
dataset and get back a grounded answer, which they can save.

## Phase 5 — Dashboards & Visualization ✅

- [x] Chart rendering on top of query results, via ECharts. A dashboard
      chart carries no data of its own — it's a `dataset_id` +
      `DatasetQueryRequest` (the same structured shape Phase 3/4 already
      use), re-run through the existing `/datasets/{id}/query` endpoint
      each time the dashboard loads. Bar and line only — pie/donut is a
      documented anti-pattern for this kind of comparison data, so it was
      deliberately left out; every chart shares one y-axis (never
      dual-axis) with colors assigned from a fixed, CVD-validated
      categorical order (`lib/chart-theme.ts`, `lib/chart-options.ts`).
- [x] Save a chart/analysis to a dashboard — `AddToDashboardControl`
      (`components/dashboards/`), reused from both the dataset explorer
      and the AI analyst so "add to dashboard" behaves identically from
      either place; can create a new dashboard inline or add to an
      existing one.
- [x] Dashboard canvas: arrange, edit, and revisit saved charts —
      `/workspace/dashboards/:id` renders each chart in a responsive grid
      with move-up/move-down (ordinal `position`) and delete controls.
- [x] Dashboards placeholder becomes real: list page
      (`/workspace/dashboards`) with create/delete, linking into the
      canvas above.

**Exit criteria:** a user can save an analysis as a chart and assemble
multiple charts into a dashboard they can revisit.

## Phase 6 — Hardening & Deployment (partial — see Deferred)

- [ ] Background workers for long-running ingest/query jobs (`app/workers`,
      still empty) — **deferred by choice**: profiling/AI-ask stay
      synchronous until they're an actual bottleneck; see Deferred below.
- [x] CI pipeline (`.github/workflows/ci.yml`): a `backend` job (ruff,
      mypy, `alembic upgrade head` + pytest against a real Postgres
      service container) and a `frontend` job (oxlint, tsc, `npm run
      build`), on every push to `main` and every PR.
- [x] Secrets management / non-dev `SECRET_KEY`: `Settings` now has a
      `model_validator` that refuses to construct at all when
      `ENVIRONMENT=production` and `SECRET_KEY` is still the insecure
      placeholder, or when `DEBUG=true` — a misconfigured production
      deploy fails loudly at import time instead of silently signing JWTs
      with a secret that's sitting in this repo's `.env.example`.
      (R2 production storage itself needed no new code — the provider's
      been there since Phase 2; it's just unset credentials away from use.)
- [x] Observability: every request now gets a `request_id`, bound to
      structlog's contextvars for the request's lifetime (so every log
      line emitted anywhere during it — service, repository, wherever —
      carries the same id with no plumbing) and echoed back as an
      `X-Request-ID` response header. Logs `request_completed` /
      `request_failed` with method/path/status/duration.
      External error tracking (Sentry or similar) intentionally not
      added — it needs a real account/DSN to be worth wiring up, so it
      waits alongside deployment.
- [ ] Deployment (target environment TBD) — **deferred by choice**: no
      target chosen yet; see Deferred below.

**Exit criteria:** the app can be deployed and operated outside a local
Docker Compose setup with confidence. Not fully met — deployment itself
still needs a target (see below).

### Deferred (deliberately, not forgotten)

- **Background workers**: skipped for now rather than picking a stack
  (in-process `BackgroundTasks` vs. a real Redis-backed queue) with
  nothing concrete yet to justify the complexity. Revisit once
  profiling/AI-ask latency is actually a problem, or once a deployment
  target makes "a separate worker process" a real, deployable thing
  rather than a local-only abstraction.
- **Deployment**: skipped until there's an actual target (Fly.io,
  Railway, a VPS, ...) and accounts to work with — writing deploy config
  against a guess would likely be thrown away. Pick a target, then this
  reopens.

---

## Notes

- Phase boundaries above match the `phase N+` comments already left in the
  code (`requirements.txt`, `config.py`, `router.py`) — those comments are
  the seams to build along, not just documentation.
- Storage, analytics, and AI each already have an empty package
  (`app/storage`, `app/analytics`, `app/ai`) reserved for their phase.
