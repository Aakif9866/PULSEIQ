# Architecture

What's actually implemented, not an aspirational diagram. Where something
is a documented future step rather than working code, it's labeled
**(planned)**.

## A note before anything else: no DuckDB, no generated SQL

Several docs and prompts around this project (including the brief this
file was written from) describe an "AI → SQL → DuckDB" pipeline. **That
pipeline doesn't exist in this codebase.** `duckdb` is a `requirements.txt`
dependency and nothing else — `grep -r duckdb backend/app` finds no
imports. The real pipeline is:

question → Groq (JSON mode) → a small, closed Pydantic schema
(`DatasetQueryRequest`: group_by / aggregations / filters / sort / limit,
every column name validated against the dataset's real schema) → executed
against a **Polars** DataFrame → result → Groq again for a plain-language
summary.

There is no free-form SQL anywhere, generated or otherwise — which also
means there's no SQL injection surface to defend (see `SECURITY.md`).
DuckDB stays in `requirements.txt` for if/when raw-SQL analysis is ever
actually wanted; it is not silently unused by accident, it's unused by
design so far.

## System overview

```
                    User
                      │
                      ▼
          React 19 + TypeScript Frontend (Vite)
                      │  fetch() over HTTPS, JWT bearer token
                      ▼
                 FastAPI API (backend/app)
                      │
          ┌───────────┼────────────┐
          │           │            │
          ▼           ▼            ▼
      PostgreSQL   Analytics       AI
      (Neon or     Engine        Provider
       any host)   (Polars)      (Groq)
                      │
                      ▼
               StorageProvider
                      │
          ┌───────────┴───────────┐
          │                       │
          ▼                       ▼
 LocalStorageProvider      R2StorageProvider
       ACTIVE                  IMPLEMENTED,
                             NOT YET IN USE
```

Postgres holds application data only: users, dataset *metadata* (filename,
size, profile, status), insights, dashboards, dashboard charts. It never
holds the uploaded dataset's actual rows — those live only in whatever
`StorageProvider` is active, loaded into memory as a Polars DataFrame on
demand for profiling, querying, or AI analysis, and never cached to a
second location.

## Frontend

React 19 + Vite + TypeScript, Tailwind CSS v4, Zustand (auth session
store, persisted to `localStorage`), TanStack Query (all server state —
no separate app-level cache), ECharts (bar/line charts on dashboards),
React Router.

Structure: `pages/` (one file per route), `components/` (layout, landing,
small `ui/` primitives — no component library), `features/<domain>/api.ts`
(TanStack Query hooks per backend resource: auth, datasets, ai, insights,
dashboards), `lib/` (the typed `fetch` wrapper, chart theming/option
building, small utilities), `stores/` (Zustand), `types/` (hand-written,
matching the backend's Pydantic schemas — no codegen).

## Backend

FastAPI, layered: `api/v1/*.py` (routes — parse request, call a service,
translate domain exceptions to HTTP status codes, nothing else) →
`services/*.py` (business logic, orchestration) → `repositories/*.py`
(the only layer that touches SQLAlchemy) → `models/*.py` (ORM) /
`schemas/*.py` (Pydantic request/response shapes). `core/` holds config,
the DB session, JWT/password hashing, structured logging, the request-
logging middleware, and domain exceptions. `analytics/` and `ai/` sit
beside `services/` as the Polars and Groq integrations respectively —
neither imports FastAPI or knows it's being called from an HTTP request.

## Authentication

JWT (HS256, `python-jose`), issued as an access/refresh pair on
signup/login. Passwords hashed with bcrypt (`passlib`). `get_current_user`
(a FastAPI dependency, `app/api/deps.py`) decodes and validates the bearer
token on every protected route; there is no session state on the server —
a token is valid until it expires or the app restarts with a different
`SECRET_KEY`. See `SECURITY.md` for the full model and its limitations.

## Dataset upload flow

```
User Upload
    ↓
File validation (extension allowlist, size limit — app/services/dataset_service.py)
    ↓
StorageProvider.save() — file written first
    ↓
Dataset metadata row created (Postgres) — referencing the storage key
    ↓  (if this insert fails, the just-saved file is deleted again — no orphan)
Profiling (app/analytics/profiling.py, via Polars) — synchronous, in the same request
    ↓
Dataset marked "profiled" (or "profiling_failed", gracefully, without failing the upload)
```

Profiling runs synchronously today (no background job queue exists yet —
see `PHASES.md` Phase 6). For a small/medium file this is fast enough to
return in the same HTTP response; a very large file would hold the
request open for the full profiling duration.

## Analytics flow (dataset explorer / dashboard charts)

```
Structured query request (group_by / aggregations / filters / sort / limit)
    ↓
Column-name validation against the dataset's real schema
    ↓
StorageProvider.open() → Polars DataFrame (re-loaded fresh each call)
    ↓
Polars group_by / agg / filter / sort (app/analytics/query_engine.py)
    ↓
Row cap enforced (QUERY_ROW_LIMIT, always, regardless of what was requested)
    ↓
Result — bounded by a wall-clock timeout (QUERY_TIMEOUT_SECONDS) via a thread pool
```

The timeout is an **HTTP-level guard**, not a true compute-killing cancel —
Python can't forcibly stop a running native Polars call. A real
cancellation would need an out-of-process worker (planned, Phase 6).

## AI analytics flow

```
User question (+ the dataset's column profile: names, dtypes, row count)
    ↓
Groq (JSON mode) → a DatasetQueryRequest — same schema as above
    ↓
Pydantic validation + column-existence check (identical safety path to a
hand-built query — the AI gets no special access or bypass)
    ↓
Executed exactly as above (Polars, row-capped, timeout-guarded)
    ↓
Result (columns, rows, row count, truncated flag)
    ↓
Groq again: question + the actual computed result → plain-language answer
    ↓
Answer shown to the user; optionally saved as an Insight or a dashboard chart
```

See `AI_ANALYTICS.md` for the safety details (why two Groq calls, what the
model can and can't do, and how a hallucinated "I deleted your data"
answer was found and fixed).

## Storage abstraction

Covered in full in `STORAGE.md`. In one line: everything above depends on
`StorageProvider` (an abstract interface — `save`/`open`/`exists`/`delete`/
`local_path`), never on `LocalStorageProvider` or `R2StorageProvider`
directly, and never on a raw filesystem path. Switching from local disk to
R2 is a `.env` change (`STORAGE_PROVIDER=r2` + four `R2_*` values), not a
code change.

## Database responsibilities

PostgreSQL (via SQLAlchemy + Alembic migrations) owns: `users`,
`datasets` (metadata + the JSON column profile, not the data itself),
`insights` (saved AI Q&A, with the structured query that produced it),
`dashboards` and `dashboard_charts` (a saved query + chart type, re-run
live each time the dashboard loads — no chart image or data snapshot is
stored). Foreign keys from `insights`/`dashboard_charts` to `datasets` are
`ON DELETE CASCADE`, so deleting a dataset correctly removes anything that
referenced it.

## Security boundaries

Full detail in `SECURITY.md`. The short version: every dataset/insight/
dashboard/chart query is scoped to `owner_id = current_user.id` at the
repository layer — there is no endpoint that returns another user's data,
verified directly (cross-tenant requests get a `404`, not a `403`, so a
user can't even confirm another user's resource exists). Storage keys are
never derived from client input. The AI has no path to mutate data and no
elevated database access beyond what the structured query schema already
allows any user to do themselves.
