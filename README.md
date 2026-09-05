# PulseIQ

AI-powered, self-service analytics platform. Upload a CSV or Excel file,
explore it without writing a query, ask questions about it in plain
language, and save the answers as charts on a dashboard.

## Key features

- **Auth** — JWT-based signup/login, per-user data isolation throughout
- **Dataset upload & profiling** — CSV/XLSX, automatic schema/dtype/null
  detection right after upload
- **Dataset explorer** — filter, sort, group, and aggregate without
  writing a query
- **AI analyst** — ask a question in plain language; answers are grounded
  in an actually-executed, validated query, not a guess (see
  [`docs/AI_ANALYTICS.md`](docs/AI_ANALYTICS.md))
- **Saved insights & dashboards** — save an AI answer, or turn any query
  into a bar/line chart on a dashboard
- **Swappable storage** — local disk today, Cloudflare R2 later, with no
  code change (see [`docs/STORAGE.md`](docs/STORAGE.md))

## Tech stack

| Layer     | Tech |
| --------- | ---- |
| Backend   | FastAPI, SQLAlchemy + Alembic, PostgreSQL, JWT auth (`python-jose`) |
| Analytics | Polars (structured queries — no generated SQL; see [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)) |
| Storage   | Local filesystem (active) or Cloudflare R2 via boto3 (implemented, not yet in use) |
| AI        | Groq, toggled off gracefully by default via `AI_PROVIDER=none` |
| Frontend  | React 19, Vite, TypeScript, Tailwind CSS v4, Zustand, TanStack Query, ECharts |

## Architecture overview

```
User → React frontend → FastAPI → PostgreSQL / Analytics (Polars) / AI (Groq)
                                        │
                                  StorageProvider
                                   ┌────┴────┐
                              Local (now)   R2 (later)
```

Full detail, including the exact dataset/AI/query flows: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Quick start

### Docker Compose

There's no local Postgres container — `DATABASE_URL` in `.env` points at
a real Postgres instance (e.g. [Neon](https://neon.tech), or any other
provider/self-hosted instance), the same one native runs use. One
database, not two to keep in sync.

```bash
cp .env.example .env   # fill in DATABASE_URL and any other real values
docker compose up --build
```

- Frontend: http://localhost:5173
- Backend: http://localhost:8000 (docs at `/docs`)

### Run natively (no Docker)

```bash
# backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
alembic upgrade head
uvicorn app.main:app --reload

# frontend, separate terminal
cd frontend
npm install
npm run dev
```

## Environment setup

All configuration is via environment variables — see
[`.env.example`](.env.example) for the full, current list (secrets,
database URL, storage provider, upload limits, AI provider). Copy it to
`.env` and fill in real values; `.env` is git-ignored and must never be
committed.

## Documentation

| Doc | Covers |
| --- | ------ |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | System design, every major flow (upload, analytics, AI), what's real vs. planned |
| [`docs/AI_ANALYTICS.md`](docs/AI_ANALYTICS.md) | The Groq pipeline, prompt design, safety controls, what's *not* built |
| [`docs/STORAGE.md`](docs/STORAGE.md) | The storage abstraction, local-mode limitations, exact R2 migration steps |
| [`docs/SECURITY.md`](docs/SECURITY.md) | The real security model and its known limitations |
| [`docs/TESTING.md`](docs/TESTING.md) | Running the app and its test suites, verified end-to-end flows |
| [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) | Deployment requirements — what's verified (Docker Compose, locally) vs. not (any cloud platform) |
| [`docs/BUGS.md`](docs/BUGS.md) | The full, dated issue tracker — every bug found, root cause, fix, and how it was re-verified |
| [`docs/PHASES.md`](docs/PHASES.md) | The phased build plan this project followed |
| [`docs/PROGRESS.md`](docs/PROGRESS.md) | The dated build log |

## Testing & linting

```bash
# Backend
cd backend && pytest
ruff check .
mypy app

# Frontend
cd frontend
npm run typecheck
npm run lint
```

See [`docs/TESTING.md`](docs/TESTING.md) for what's actually been verified
end-to-end, not just unit-tested.
