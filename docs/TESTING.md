# Testing

How to run the app locally and its test suites, and where the detailed
issue history lives.

## Start the application locally

See the root `README.md` for full Docker/native instructions. Short
version:

```bash
# Docker Compose (needs DATABASE_URL in .env pointing at a real Postgres —
# Neon, Supabase, RDS, or your own; no local Postgres container is run)
cp .env.example .env
docker compose up --build

# or natively
cd backend && python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
alembic upgrade head
uvicorn app.main:app --reload
# separately:
cd frontend && npm install && npm run dev
```

## Run the backend tests

```bash
cd backend
source .venv/bin/activate
export DATABASE_URL=postgresql+psycopg://pulseiq:pulseiq@localhost:5432/pulseiq  # a real, reachable Postgres
alembic upgrade head
pytest            # 48 tests as of this writing
ruff check .
mypy app
```

Tests run against a **real Postgres** (no sqlite substitution — the app
uses Postgres-specific types like `JSONB`), wrapped in a per-test
transaction that's rolled back afterward (`tests/conftest.py`), so tests
never leave data behind. AI tests mock the two Groq calls
(`app.services.analyst_service.build_query_from_question`/
`summarize_result`) so the suite stays deterministic and doesn't require
a real API key or network access to pass in CI.

Test files, one per resource area: `test_auth.py`, `test_datasets.py`,
`test_dataset_query.py`, `test_ai_analyst.py`, `test_dashboards.py`,
`test_storage.py`, `test_config.py`, `test_health.py`.

## Run the frontend checks

```bash
cd frontend
npm run typecheck   # tsc -b --noEmit
npm run lint         # oxlint
npm run build         # full production build
```

**No frontend automated test suite exists** (no Vitest/Jest/Playwright/RTL
configured) — this is a known, stated gap, not an oversight. Frontend
correctness has been verified through `tsc`/`oxlint`/successful builds and
manual code review, plus real end-to-end HTTP-level testing of every flow
the frontend calls (see below) — not through automated UI tests.

## CI

`.github/workflows/ci.yml` runs the backend suite (against a real Postgres
service container) and the frontend checks on every push to `main` and
every pull request.

## Important end-to-end flows (verified live, not just unit-tested)

The primary user journey — signup → login → upload CSV → upload XLSX →
verify storage → profiling → explore/query → ask the AI analyst → save an
insight → build a dashboard chart → simulate a refresh → delete a dataset
→ verify cascade cleanup → confirm protected routes reject an unauth'd
request — has been run end-to-end against a real external Postgres (Neon)
and the real Groq API multiple times across this project's development,
including once fully through Docker Compose's containerized nginx `/api`
proxy (not just natively).

### Dataset upload testing

Both CSV and XLSX, plus failure cases: empty file, header-only file,
single-row file, missing values, ragged/malformed rows, duplicate column
names, unicode content, a corrupted `.xlsx` (random bytes with the right
extension), an oversized file (against a temporarily lowered limit), and
a simulated database failure mid-upload. Every failure case leaves zero
orphaned database rows and zero orphaned files — verified directly by
listing storage contents before/after, not assumed.

### AI analytics testing

Simple questions, ambiguous questions ("what's performing badly?"),
impossible questions (no hallucination), misspelled/nonexistent columns,
direct and data-embedded prompt injection (both refused/quoted-not-
followed), and a request to mutate data (refused, with a fix applied
after the first version hallucinated that it had succeeded — see
`docs/BUGS.md`).

### Regression testing

Re-run after every fix in this project's history: the full pytest suite,
`ruff`/`mypy`/`tsc`/`oxlint`/frontend build, and the primary user journey
above. See `docs/BUGS.md` for the complete, dated record of every issue
found, its root cause, the fix applied, and how it was re-verified —
this file only summarizes; that one is the detailed history.
