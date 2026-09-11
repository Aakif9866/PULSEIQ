# PulseIQ V2 — Future Architecture

**Mostly planning, with one exception:** the Monitoring Service described
below (AI Anomaly Monitoring / Data Pulse) is implemented on the
`feature/pulseiq-v2-roadmap` branch — not merged, not deployed. Everything
else in this document shows how the system's *shape* could still evolve,
based on the actual V1 architecture (`docs/ARCHITECTURE.md`), not a generic
target architecture. Where V2 adds nothing structurally new, that's stated
explicitly rather than invented for symmetry.

## CURRENT V1

```
React Frontend (Vite build, served by nginx)
        |
        | HTTPS / JSON over REST (/api/v1/*)
        v
FastAPI Backend
        |
        +----------------> Authentication (JWT, bcrypt)
        |
        +----------------> Neon PostgreSQL (users, datasets, insights, dashboards)
        |
        +----------------> StorageProvider (local disk today, R2-ready)
        |
        +----------------> Polars Analytics Engine (profiling + structured queries)
        |
        +----------------> Groq AI (question -> structured query -> grounded answer)
```

One FastAPI process, one database, one analytics engine (Polars), one AI
provider. No message queue, no cache, no separate worker process, no second
database. Two Railway services total: the backend above, and the static
frontend build served by nginx.

## PROPOSED V2

```
React Frontend
        |
        v
FastAPI API Layer
        |
        +-- Authentication                          [CURRENT V1 — unchanged]
        |
        +-- Dataset Service                          [CURRENT V1 — extended: profiling depth, versioning]
        |
        +-- Analytics Service                        [CURRENT V1 — extended: DuckDB alongside Polars]
        |
        +-- AI Service                                [CURRENT V1 — extended: SQL generation, chart suggestion]
        |
        +-- SQL Validation Layer                     [PROPOSED V2 — new]
        |
        +-- Dashboard Service                        [CURRENT V1 — extended: layout/filters]
        |
        +-- History Service                          [PROPOSED V2 — new]
        |
        +-- Monitoring Service                       [IMPLEMENTED — new]
                 |
        +--------+--------+-------------------+
        |                 |                   |
        v                 v                   v
Neon PostgreSQL   Object Storage         DuckDB Analytics Engine
(unchanged,        (R2 — already          (PROPOSED V2 — new,
more tables,        written, finally       runs alongside Polars,
incl. monitors/     used in prod)          not replacing it)
anomalies —
IMPLEMENTED)
        |
        v
Groq AI
(unchanged provider, three new prompt types:
 SQL generation, chart-type suggestion,
 anomaly explanation — IMPLEMENTED)


           [external scheduler, e.g. Railway cron]
                          |
                          v
           app.workers.anomaly_runner (CLI entrypoint,
           same Docker image — IMPLEMENTED, not yet
           wired to an actual schedule — see below)
```

## What's genuinely new vs. what's the same shape, doing more

| Layer | Status | Explanation |
|---|---|---|
| React Frontend | **Unchanged shape** | Still one SPA, same routing/state pattern (TanStack Query + Zustand); new pages/components (SQL Explorer, richer dashboard editor) fit inside the existing `pages/` + `features/` structure |
| FastAPI API Layer | **Unchanged shape** | Still one process, same router → service → repository layering; new routers (e.g. `/datasets/{id}/sql`, `/history`) added the same way every existing router was |
| Authentication | **CURRENT V1 — unchanged** | Nothing in this roadmap requires a new auth model |
| Dataset Service | **Extended** | Same service, deeper profiling, optional versioning — no new service boundary |
| Analytics Service | **Extended** | Gains a second execution backend (DuckDB) alongside Polars — described in detail below |
| AI Service | **Extended** | Same `app/ai` module, two new prompt/response shapes (SQL text instead of structured JSON; a chart-type enum) — same two-call, JSON-mode-where-possible pattern V1 already established |
| SQL Validation Layer | **New** | The one genuinely new architectural component — sits between the AI Service and the Analytics Service, and is also what the SQL Explorer calls directly (bypassing AI generation, not bypassing validation) |
| Dashboard Service | **Extended** | Same service, new fields (`layout`, `filters`) on the same entities |
| History Service | **New** | A thin service around the new `QueryHistory`/`SavedQuery` tables (see `docs/V2_DATABASE_PLAN.md`) — no new architectural pattern, just a new entity following the existing repository pattern |
| Monitoring Service | **New, implemented** | `app/services/monitor_service.py` — the same router → service → repository pattern as every other V1 entity, plus one new AI-free module (`app/monitoring/detection.py`) with no HTTP or database concerns at all. Confirms the "layer separation" principle this whole document argues for actually holds up when a fifth service is added |
| Neon PostgreSQL | **Unchanged** | Same database, same connection handling, more tables (`monitors`, `anomalies` — implemented) |
| Object Storage | **Unchanged code, changed status** | `R2StorageProvider` already exists and is unit-tested; V2 is about actually running it with real credentials in production, not writing new code |
| DuckDB Analytics Engine | **New usage of an existing dependency** | Not a new dependency — already in `requirements.txt`, unused today; V2 is the first time it's actually imported and called |
| Groq AI | **Unchanged provider** | Same SDK, same client wrapper (`app/ai/groq_client.py`), new prompts only |

## Why no new services, queues, or databases are proposed

Every V2 feature in `docs/V2_ROADMAP.md` can be built as a new function, a
new router, and a handful of new tables inside the exact same FastAPI
process and Neon database V1 already runs. Deliberately **not** proposed,
and why:

- **A message queue / background workers** — nothing in V2 requires
  long-running or delayed processing. SQL execution is bounded (same
  timeout pattern as V1's Polars queries); profiling extensions are still
  fast, synchronous Polars operations. Anomaly monitoring — the one V2
  feature that sounds most like it needs a "worker" — was deliberately
  built as a plain CLI entrypoint instead
  (`app/workers/anomaly_runner.py`), meant to be invoked by an external
  scheduler rather than run as a long-lived process inside the app. No
  Celery, no Redis, no queue: confirmed, not just planned. If dataset sizes
  grow enough that bounded, synchronous execution stops being true, that's
  a real future need — but it's not a V2 requirement, and adding a queue
  speculatively would be exactly the kind of unrealistic, resume-driven
  complexity this roadmap is trying to avoid.
- **A cache layer (Redis, etc.)** — genuinely useful eventually (V1 re-loads
  a dataset from storage on every query), but no V2 feature here strictly
  requires it. Worth flagging as the natural *next* addition after V2, not
  part of it (see `docs/PULSEIQ_SKILLS.md`'s skill-gap section for the same
  conclusion from a different angle).
- **A second database** — DuckDB in V2 is used as an **in-process, embedded
  engine**, operating on data already loaded into memory (the same Polars
  DataFrame, registered as a DuckDB view) — not a separately-hosted database
  with its own connection lifecycle. This is DuckDB's actual intended use
  case (embedded analytics), not a workaround.
- **Microservices** — one FastAPI process remains the right size for this
  project. Splitting the AI service or SQL validation layer into a separate
  deployable would add real operational complexity (service discovery,
  network calls where a function call currently works, a second thing to
  deploy on Railway) for no benefit at this project's actual scale.

## How DuckDB and Polars coexist (the one real engine-level change)

Polars keeps its current job unchanged: loading files, computing the
profile, and executing every *structured* query (V1's existing
`group_by`/`aggregations`/`filters` schema — the manual query builder never
needs to change). DuckDB is added specifically for the SQL path: the same
in-memory Polars DataFrame is registered as a DuckDB view
(`duckdb.sql("SELECT * FROM df")`-style, no separate load/parse step, no
data duplication), and only validated `SELECT` statements are ever executed
against that view, through a fresh, disposable connection per query. Neither
engine reads the other's output format directly — DuckDB can query a Polars
DataFrame natively via Arrow, which is what makes this pairing worth having
instead of just picking one.

## Deployment — unchanged, with one deferred addition

No new Railway service was required to build or test anomaly monitoring —
it lives entirely inside the existing backend image, reachable over the
existing API for everything except the scheduler. The only deployment
question this feature actually raises is how `app/workers/anomaly_runner.py`
gets invoked *periodically* in production, and that's deliberately left
unanswered here: Railway supports a native cron-scheduled service
(`deploy.cronSchedule`), which would be a second, lightweight Railway
service built from the exact same Docker image with this script as its
start command — no new infrastructure category, just one more entry in the
same project. Setting that up is a real production deployment change
(touching the live Railway project), so it wasn't done as part of this
planning-and-build task; `run_due_monitors()` is fully implemented and
callable, just not yet wired to fire on a schedule. New environment
variables are limited to what the feature's own config needs
(`SMTP_HOST`/`SMTP_PORT`/`SMTP_USERNAME`/`SMTP_PASSWORD`/`SMTP_FROM_EMAIL`/
`SMTP_USE_TLS` — all optional, email alerting simply stays off if unset).
Everything else (SQL query timeout settings, etc.) remains as originally
planned for the rest of V2.
