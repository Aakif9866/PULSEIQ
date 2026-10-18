# AGENTS.md — PulseIQ

Shared coding-agent instructions for any AI assistant working in this repo.

## Project

PulseIQ — upload a spreadsheet, ask questions in plain English, get answers
computed by deterministic tools (never by the LLM) and cross-checked by an
answer validator. The model picks tools; 16 Polars-based tools compute;
DuckDB runs NL-to-SQL; a validator verifies every finding.

## Tech stack

| Layer | Technology | Version constraint |
|---|---|---|
| Backend | Python 3.12, FastAPI, Pydantic v2 | pinned in `backend/requirements.txt` |
| Database | PostgreSQL 16 (Neon in prod) | migrations via Alembic |
| Analytics | Polars, DuckDB, sqlglot (AST-based SQL validation) | |
| AI provider | Groq (tool-calling loop) | configurable; `AI_PROVIDER=none` disables |
| Frontend | React 19, TypeScript 6, Vite 8, Tailwind CSS 4 | pinned in `frontend/package.json` |
| State | TanStack Query (server), Zustand (client) | |
| Charts | ECharts via echarts-for-react | |
| UI | Radix primitives, Lucide icons, Framer Motion | |
| Lint (backend) | Ruff (`E,F,I,UP,B`), line-length 100 | |
| Lint (frontend) | oxlint | |
| Typecheck | mypy (backend), tsc (frontend) | |
| Tests | pytest + pytest-asyncio (backend), Vitest (frontend) | |
| Eval harness | `evals/` — 51 questions, ground truth from app's own tools | |
| Deployment | Docker (backend + frontend images), Render blueprint | |
| Storage | Cloudflare R2 (prod) or local filesystem (dev) | |
| Tracing | OpenTelemetry (optional, OTLP/HTTP) | |
| CI | GitHub Actions — see `.github/workflows/ci.yml` | |

## Repository layout

```
backend/
  app/
    ai/          # AI analyst engine, tool-calling loop, providers
    analytics/   # 16 deterministic tools, SQL validator, SQL engine
    api/         # FastAPI route modules
    core/        # Config, auth, tracing, error tracking, middleware
    models/      # SQLAlchemy ORM models
    monitoring/  # Anomaly detection
    repositories/
    schemas/     # Pydantic request/response schemas
    services/
    storage/     # StorageProvider (local / R2)
    utils/
    workers/     # Background tasks, demo data seeding
  alembic/       # DB migrations
  tests/         # pytest suite
frontend/
  src/
    components/  # Presentational (ui/, ai/, dashboards/, datasets/, sql/, layout/, landing/)
    features/    # Feature modules (auth, ai, dashboards, datasets, history, insights, monitors, usage)
    lib/         # Shared utilities (API client, etc.)
    pages/       # Route-level page components
    stores/      # Zustand stores
    types/       # TypeScript type definitions
evals/           # Evaluation harness (datasets, questions, runner, ground truth)
docs/            # Architecture, security, testing, roadmap docs
```

## Architecture constraints

1. **The model never computes a number.** LLM picks tools → deterministic tools compute → answer validator cross-checks findings against tool output. Never let the LLM return computed values directly.
2. **NL-to-SQL is safe by construction.** SQL is parsed via sqlglot AST → must be a single SELECT over the user's dataset with known columns, standard functions, and clamped LIMIT. DuckDB runs with external access disabled. Do not weaken these constraints.
3. **Per-user data isolation.** Every query is scoped to the authenticated user's datasets. Do not introduce cross-user data access paths.
4. **Storage is provider-agnostic.** All file I/O goes through `StorageProvider`. Never write direct filesystem calls for upload/download logic.
5. **AI is optional.** `AI_PROVIDER=none` disables AI features gracefully. All non-AI features must work without it.

## Development commands

### Backend (run from `backend/`)

```sh
# Activate venv
source .venv/bin/activate  # or create: python3.12 -m venv .venv && pip install -r requirements-dev.txt

# Run dev server
uvicorn app.main:app --reload --port 8000

# Lint
ruff check .

# Typecheck
mypy app

# Run migrations
alembic upgrade head

# Create migration
alembic revision --autogenerate -m "description"

# Tests
pytest
```

### Frontend (run from `frontend/`)

```sh
npm ci          # install deps (use ci, not install)
npm run dev     # dev server (Vite)
npm run lint    # oxlint
npm run typecheck  # tsc --noEmit
npm test        # vitest run
npm run build   # production build
```

### Docker

```sh
docker compose up --build    # both services
docker build -t pulseiq-backend:dev backend
docker build -t pulseiq-frontend:dev frontend
```

### Evals (run from `evals/`)

```sh
python -m pytest -q              # harness tests (no API calls)
python runner.py                 # live eval run (uses Groq quota)
python build_datasets.py         # regenerate sample datasets
```

## CI pipeline (`.github/workflows/ci.yml`)

Runs on push to `main` and all PRs. Four jobs, all must pass:

1. **Backend** — ruff check, mypy, alembic upgrade head, pytest (with Postgres 16 service)
2. **Frontend** — oxlint, tsc, vitest, vite build
3. **Evals** — ruff check on evals/, harness tests, dataset determinism check, ground truth computation for all 51 questions, demo dataset matches eval dataset
4. **Docker** — both images build successfully

## Coding conventions

### Backend (Python)
- Ruff rules: `E,F,I,UP,B` (ignore `B008` for FastAPI `Depends()`)
- Line length: 100
- Target: Python 3.12
- Use Pydantic models for request/response schemas
- Use SQLAlchemy ORM models (not raw SQL) for Postgres operations
- Use Polars for in-memory analytics, DuckDB for user SQL queries
- Structured logging via `structlog`

### Frontend (TypeScript/React)
- Strict TypeScript (tsc must pass)
- TanStack Query for all server state
- Zustand for client-only state
- Tailwind CSS 4 for styling
- Components in `components/`, feature logic in `features/`

## Testing requirements

- Backend changes: add or update tests in `backend/tests/`
- Security-sensitive changes (SQL validation, auth, data isolation): must have regression tests
- Eval-affecting changes (tool output shape, new tools): update `evals/` ground truth
- Frontend: add tests in `frontend/src/test/` for non-trivial logic

## Security rules

- **SQL injection**: all user SQL goes through sqlglot AST validation then DuckDB with external access off. Never bypass the validator.
- **Auth**: JWT-based, every endpoint requires auth unless explicitly public. Never expose unauthenticated data endpoints.
- **Secrets**: never commit `.env`. Use `.env.example` for documentation. CI uses its own secrets.
- **File uploads**: validated by size (`MAX_UPLOAD_SIZE_MB`) and routed through `StorageProvider`. Never write user uploads to arbitrary paths.
- **Rate limiting**: enabled by default. Do not disable in production config.

## Git safety

- Do not force-push to `main`
- Do not commit `.env`, credentials, or API keys
- Do not amend published commits without explicit permission
- Always ask before committing or pushing (per project memory rule)
- Run `git status` before any destructive git operation

## Environment variables

See `.env.example` for the full list with documentation. Key ones:
- `DATABASE_URL` — Postgres connection string
- `AI_PROVIDER` — `groq` or `none`
- `GROQ_API_KEY` — required when `AI_PROVIDER=groq`
- `STORAGE_PROVIDER` — `local` or `r2`
- `ENVIRONMENT` — `development`, `test`, or `production`
