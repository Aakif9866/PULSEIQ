# PulseIQ Bug & Improvement Tracker

## Summary

Total Issues Found: 12 (running total — updated as testing proceeds)

Critical: 1
High: 5
Medium: 6
Low: 0

**A note on scope and honesty:** this environment has no browser-automation
tool (no Playwright/Puppeteer/screenshot capability). Backend, API, AI
pipeline, security, and data-integrity findings below are from actually
running the app and issuing real requests against it — not just reading
code. Frontend findings are from careful code review of every page/component
(all of which were written this session) since I cannot click through the UI
myself; those are labeled "code review" rather than "tested" throughout, per
the instruction not to claim interactive testing that didn't happen.

**Architecture note, relevant to several sections of the QA brief:** PulseIQ
does not use DuckDB or generate SQL anywhere. The actual pipeline is:
question → Groq (JSON mode) → a `DatasetQueryRequest` (a closed Pydantic
schema: group_by/aggregations/filters/sort/limit, column names validated
against the real schema) → executed via Polars → result → Groq again for a
plain-language summary. `duckdb` is in `requirements.txt` but unused in
`app/` — reserved, per the code's own comments, for if/when free-form SQL is
ever needed. This means "SQL injection" and "generated SQL" sections of the
brief don't map onto a real attack surface here (there is no SQL, generated
or otherwise) — instead I tested the analogous risk: can a question or
injected dataset content make the AI produce a mutating action or leak
config? See BUG entries under AI/Security below.

---

## BUG-001 — Backend cannot start against a standard `postgresql://` connection string (e.g. Neon, Supabase, RDS)

**Severity:** Critical

**Area:** Backend / Database / Deployment

**Status:** FIXED

### Description

The app failed to even import when `DATABASE_URL` is a plain
`postgresql://...` URL — the format every managed Postgres provider hands
out by default (Neon included, confirmed with the user's real Neon
connection string). SQLAlchemy resolves a driver-less `postgresql://` scheme
to the legacy `psycopg2` dialect, but the project only installs `psycopg`
(v3) — `psycopg2` isn't in `requirements.txt` and isn't installed.

### Steps to Reproduce

1. Set `DATABASE_URL=postgresql://<user>:<pass>@<neon-host>/<db>?sslmode=require&channel_binding=require` in `.env` (Neon's own copy-paste format).
2. Run anything that imports `app.core.database` (e.g. `alembic current`, or start `uvicorn app.main:app`).

### Expected Behavior

The app connects using whatever standard Postgres URL a hosting provider
supplies, without requiring the user to hand-edit the scheme.

### Actual Behavior

```
ModuleNotFoundError: No module named 'psycopg2'
```
raised from `sqlalchemy/dialects/postgresql/psycopg2.py` during
`create_engine()` — the app cannot start at all.

### Root Cause

`app/core/database.py` passed `settings.DATABASE_URL` straight into
`create_engine()` with no normalization. The project's own `.env.example`
happens to spell the local-dev default as `postgresql+psycopg://`, which
masked this for the entire project so far — every previous test this
session used that exact local value. The instant a real external
connection string (Neon's own, unedited) was used, it broke.

### Proposed Fix

Normalize the scheme in `Settings` itself (a `field_validator` on
`DATABASE_URL`) so `postgresql://` and the legacy `postgres://` (still
emitted by some providers, e.g. old Heroku-style URLs) are rewritten to
`postgresql+psycopg://` before anything constructs an engine. This fixes it
for every caller (the app, Alembic, tests) in one place, and requires zero
configuration changes from whoever pastes in a connection string.

### Regression Risk

Low. The validator is a no-op for any URL that already specifies a driver
(`+psycopg`, `+psycopg2`, etc.) or isn't a Postgres URL. Existing local-dev
`.env` (which already spells out `+psycopg`) is unaffected.

### Fix Applied

Added a `@field_validator("DATABASE_URL", mode="after")` to `Settings` in
`backend/app/core/config.py` that rewrites a bare `postgresql://` or
`postgres://` prefix to `postgresql+psycopg://`, leaving any URL that
already names a driver untouched.

### Verification

Verified by:
- Reproducing the original failure with the exact Neon URL from `.env`
  (`ModuleNotFoundError: No module named 'psycopg2'`) before the fix.
- After the fix: `python -c "from app.core.config import settings; print(settings.DATABASE_URL)"` shows the URL rewritten to `postgresql+psycopg://...`.
- `alembic current` / `alembic upgrade head` run successfully against the
  real Neon database (see below — Neon was empty, all 5 migrations applied
  cleanly).
- Existing local-dev `DATABASE_URL` (`postgresql+psycopg://pulseiq:pulseiq@localhost:5432/pulseiq`) confirmed unchanged by the validator (already has a driver).
- Full backend test suite re-run after the fix — still 34/34 passing (this
  validator doesn't affect the local test DB URL at all, but confirms no
  regression).

---

## BUG-002 — CSV columns with leading zeros (zip codes, product codes, IDs) silently lose the leading zero and become un-filterable by their real value

**Severity:** Medium

**Area:** Backend / Analytics / Data integrity

**Status:** FIXED

### Description

Any CSV column whose values look like plain integers but carry a leading
zero (zip codes, SKUs, employee IDs, phone extensions — `"007"`, `"094"`)
gets silently type-inferred by Polars as `Int64`, which strips the leading
zero at read time. This happens on *every* load — profiling, the dataset
explorer, AI-generated queries, dashboard charts — since they all go through
the same `load_dataframe`. The stored file itself is untouched; only every
downstream read of it is affected.

### Steps to Reproduce

1. Upload a CSV: `zip,amount\n"007",100\n"094",200\n`
2. Profile shows `zip` as dtype `Int64` (not `String`).
3. `POST /datasets/{id}/query` with `{"filters":[{"column":"zip","op":"eq","value":"007"}]}` (the value exactly as it appears in the source file).

### Expected Behavior

A filter for the value as it literally appears in the uploaded file should
match, or at minimum fail with a clear explanation — not a generic type
error that gives no hint the value was silently transformed.

### Actual Behavior

```
400 {"detail":"Filter on 'zip' could not be applied: cannot compare string with numeric type (i64)"}
```
Filtering by the *coerced* value (`7` instead of `"007"`) does match — but
nothing in the API response or the dataset's profile discloses that this
coercion happened. A user (or the AI analyst, asked "show me zip 007")
would very reasonably try `"007"` first and get a confusing error.

### Root Cause

`app/analytics/loader.py` calls `pl.read_csv(buffer)` with Polars' default
schema inference, which looks at column values and — for anything that
parses cleanly as an integer, leading zeros included — casts the whole
column to `Int64`. There is no leading-zero-aware carve-out, so `"007"` and
`7` are indistinguishable to it.

### Proposed Fix

Read CSVs with schema inference disabled (`infer_schema_length=0`, i.e.
every column comes back as `Utf8`/String), then re-cast each column to
`Int64`/`Float64` myself — except any column containing a value matching
`^-?0\d+$` (a leading zero followed by another digit), which stays a
string. This preserves normal numeric behavior for real numbers while
protecting exactly the class of values (zip/product/ID codes) where the
leading zero is semantically part of the value, not a number.

### Regression Risk

Low-medium: this changes CSV dtype inference for every dataset, including
already-uploaded ones the next time they're queried (nothing is
re-profiled automatically, so an already-profiled dataset's *stored*
`columns_profile` won't retroactively change until re-uploaded — only
fresh uploads and fresh query-time loads get the corrected inference).
Needs the full test suite re-run afterward, since `test_dataset_query.py`
and `test_ai_analyst.py` both depend on specific inferred dtypes.

### Fix Applied

`app/analytics/loader.py` now reads CSVs with `infer_schema_length=0`
(every column comes back as String, real nulls preserved as nulls — not
empty strings, verified separately), then re-casts each column to
`Int64`/`Float64` itself using `strict=False` — except any column
containing a value matching `^-?0\d+$`, which is left as String.

### Verification

Verified by:
- Re-uploading the same `zip,amount_str` CSV: `zip` now profiles as
  `String` (was `Int64`), value stored exactly as `"007"`.
- The original failing filter now succeeds:
  `{"filters":[{"column":"zip","op":"eq","value":"007"}]}` → 200,
  returns the `"007"` row.
- **Regression check**: a normal numeric column (`amount`, plain integers,
  no leading zeros) still infers as `Int64` and `sum`/`group_by` on it
  still works correctly (`A → 30`, `B → 5`).
- Full backend suite re-run after the fix — still 34/34 passing
  (`test_dataset_query.py` and `test_ai_analyst.py` both exercise numeric
  columns and continued to pass, confirming normal numeric inference is
  unaffected).
- `ruff` and `mypy` clean on the changed file (mypy needed one fix along
  the way: the dtype variable was typed as `pl.DataType | None`, but
  `pl.Int64`/`pl.Float64` are *classes*, not instances — corrected to
  `type[pl.DataType] | None`).

---

## BUG-003 — AI analyst hallucinates that a destructive action (delete/update/insert) succeeded, when the system has no such capability and nothing happened

**Severity:** High

**Area:** AI / Security / Trust

**Status:** FIXED

### Description

Asked to mutate data ("update all revenue values to zero", "delete all
records"), the AI's natural-language answer claims the action was
**completed**, in the past tense — e.g. *"All six revenue entries have been
changed to 0"* — when nothing was actually touched. This is not a real
security breach: the query engine has zero mutation operations in its
schema (`DatasetQueryRequest` only supports group_by/aggregate/filter/sort
— there is no delete/update/insert path to reach, verified below), so no
data was ever at risk. The bug is that the **answer text itself lies** about
what happened, which is a serious trust problem for a data product — a user
skimming the answer would reasonably believe their dataset was just
corrupted or wiped.

### Steps to Reproduce

1. Upload any dataset.
2. `POST /datasets/{id}/ask` with `{"question": "Update all revenue values to zero."}`
3. Read the `answer` field.
4. Re-run a real aggregation query against the same dataset to confirm the
   data is actually unchanged.

### Expected Behavior

The assistant should clearly state it can only read and analyze data, not
modify it, and that no such action was (or could be) performed.

### Actual Behavior

```
"All six revenue entries have been changed to 0. The original amounts of
1,200, 1,350, 900, 700, 650 and 300 have been replaced with zero..."
```
Re-querying the same dataset immediately afterward shows the real total
revenue unchanged (`5100`) — the claim is entirely fabricated. A milder
version of the same pattern appeared for "delete all records", which
narrated a hypothetical deletion ("would remove all of these six rows...
no data would remain") in a way that reads ambiguously.

### Root Cause

`_ANSWER_SYSTEM_PROMPT` in `app/ai/analyst.py` told the model to "write a
concise, plain-language answer" summarizing a query result, but never told
it the assistant has no mutation capability at all, or that it must not
narrate a requested mutation as if it happened (or could happen). For a
mutation-flavored question, the query-generation step correctly produces a
harmless read-only query (empty aggregations → a raw preview, or the
question's own filters) — but the *second* Groq call, writing the final
answer, sees a question that talks about deleting/updating/inserting and,
with nothing telling it not to, plays along narratively.

### Proposed Fix

Add an explicit, unambiguous instruction to `_ANSWER_SYSTEM_PROMPT`: the
assistant can only read and summarize data, has no ability to modify,
delete, or insert anything, and must say so plainly if asked — never
narrate a hypothetical or completed mutation.

### Regression Risk

Very low — purely an addition to a system prompt string; doesn't touch any
executable logic. Re-verified normal read-only questions still answer
correctly afterward.

### Fix Applied

Added to `_ANSWER_SYSTEM_PROMPT`:
*"You cannot modify, delete, add, or update any data — you can only read
and summarize it. If the question asks you to change data in any way, say
plainly that you can't and that you can only analyze the data as it is —
never describe a change as if it happened or could happen."*

### Verification

Verified by re-running the exact original prompts against the live Groq API
after the fix (backend restarted to pick up the prompt change):
- *"Update all revenue values to zero."* → now: **"I'm sorry, but I can't
  modify the data. I can only analyze it as it currently stands."** —
  clean refusal, no hallucinated completed/hypothetical mutation.
- *"Delete all records from the dataset."* → now: **"I'm sorry, but I
  can't delete records. I can only analyze the data as it currently
  exists."** — same clean pattern.
- Confirmed real read-only questions ("What is the total revenue?",
  "Which category has the highest revenue?") still answer correctly and
  concisely after the prompt change — no regression in normal behavior.
- Re-confirmed via direct query that the underlying data is, and always
  was, unaffected (`total: 5100`).

---

## BUG-004 — No React error boundary anywhere: any unhandled render error white-screens the entire app

**Severity:** Medium

**Area:** Frontend

**Status:** FIXED

*(Found by code review — `grep` confirmed no `ErrorBoundary` /
`componentDidCatch` / `getDerivedStateFromError` anywhere in `src/`. Not
interactively reproduced in a browser, since none is available in this
environment; the absence itself is the finding.)*

### Description

If any component throws during render — a null/shape mismatch on an API
response the type system didn't catch, a third-party library (ECharts)
edge case, anything — React unmounts the entire tree. With no error
boundary anywhere, the user sees a blank white page and has no in-app way
to recover; only a manual reload gets them back to a working state, and
even then whatever navigation state they had is gone.

### Steps to Reproduce

Code-review finding, not reproduced live (no browser tool). Confirmed by
inspecting every page/component in `src/` — none catches render errors,
and `main.tsx` renders `<App />` directly with nothing wrapping it.

### Expected Behavior

An unexpected render error should degrade to a contained, friendly fallback
("Something went wrong" + a reload action) rather than a blank page.

### Actual Behavior

No boundary exists; a thrown error propagates all the way to React's own
unhandled-error unmount, which shows nothing.

### Root Cause

Never added. Not a regression — the app never had one.

### Proposed Fix

Add a small class-based `ErrorBoundary` (React error boundaries must be
class components — there's no hooks equivalent) wrapping `<App />` in
`main.tsx`, rendering a plain fallback UI with a reload button when it
catches something.

### Regression Risk

Very low — purely additive; wraps the existing tree without changing any
existing component's behavior in the non-error path.

### Fix Applied

Added `frontend/src/components/error-boundary.tsx` (a class component
implementing `getDerivedStateFromError`/`componentDidCatch`, logging the
error to the console and rendering a centered fallback card matching the
app's existing dark theme, with a "Reload" button) and wrapped `<App />`
with it in `main.tsx`.

### Verification

Verified by:
- `tsc -b --noEmit`, `oxlint`, and `npm run build` all clean after adding it.
- Code review confirms it's the standard, correctly-implemented React error
  boundary API (`getDerivedStateFromError` + `componentDidCatch`, class
  component — required, there's no hooks equivalent).

**Honest limitation:** I could not interactively confirm the fallback UI
actually renders on a real thrown error — that requires a JS-executing
browser to observe, and none is available in this environment (curl can't
execute client-side React). This is a correctly-implemented instance of a
standard, very well-established React API, not novel logic, which is why
I'm still marking it FIXED rather than leaving it unverified — but
flagging plainly that the render-time behavior itself wasn't watched
happen, only built and statically checked.

---

## BUG-005 — Frontend container's own HEALTHCHECK always fails (`localhost` resolves to IPv6 first; nginx only binds IPv4)

**Severity:** Medium

**Area:** Infrastructure / Docker

**Status:** FIXED

*(Found while actually fixing and running Docker — `docker compose up`,
not code review. Docker Desktop had been unresponsive/OOM-killed since
the very start of this project; this bug only surfaces once the app is
actually run in containers, which nothing had done until now.)*

### Description

`frontend/Dockerfile`'s `HEALTHCHECK` runs `wget -qO- http://localhost/`.
Inside this image, `/etc/hosts` resolves `localhost` to both `127.0.0.1`
and `::1`; `wget` tries `::1` (IPv6) and nginx's `listen 80;` only binds
`0.0.0.0:80` (IPv4) — so the healthcheck fails with "connection refused"
every 30 seconds, forever, even though the container is completely
healthy and serving real traffic correctly.

### Steps to Reproduce

1. `docker compose up -d`
2. Wait ~90s (three failed healthcheck retries).
3. `docker compose ps` shows the `frontend` service as `unhealthy`.
4. Meanwhile `curl http://localhost:5173/` from the host, and every real
   request through it, works correctly (verified: HTTP 200, and a full
   signup call through the container's `/api` proxy to the backend
   container succeeded).

### Expected Behavior

A container that's actually serving requests correctly should report
healthy.

### Actual Behavior

```json
{"Status": "unhealthy", "FailingStreak": 3, "Log": [
  {"ExitCode": 1, "Output": "wget: can't connect to remote host: Connection refused\n"}
]}
```
Confirmed directly: `docker exec ... wget -qO- http://localhost/` fails
the same way; `docker exec ... wget -qO- http://127.0.0.1/` succeeds
immediately, returning the real `index.html`. `ss -tlnp` inside the
container confirms nginx listens on `0.0.0.0:80` only — no `[::]:80`.

### Root Cause

Classic IPv4/IPv6 loopback mismatch: `nginx.conf` has `listen 80;`
(IPv4-only — a bare port with no `[::]:80` counterpart), but the
healthcheck asks for `localhost`, which this image's resolver tries as
IPv6 first. Nothing was listening on the IPv6 loopback, so every check
was refused instantly.

### Proposed Fix

Point the healthcheck at `127.0.0.1` explicitly, bypassing hostname
resolution (and its IPv4/IPv6 ambiguity) entirely.

### Regression Risk

None — this only changes what the container's internal healthcheck
targets; doesn't touch nginx config, routing, or anything request-facing.

### Fix Applied

`frontend/Dockerfile`: `wget -qO- http://localhost/` → `wget -qO-
http://127.0.0.1/`.

### Verification

Verified by:
- Rebuilding the frontend image (`docker compose build frontend`) and
  recreating the container (`docker compose up -d`).
- `docker compose ps` now shows `frontend` as `healthy`.
- `docker inspect ... .State.Health` confirms `"Status": "healthy"` with
  successful check log entries.
- Re-confirmed real traffic still works: `curl http://localhost:5173/`
  (200) and a real signup call through the container's `/api/` proxy to
  the backend container both still succeed after the rebuild.

---

## BUG-006 — No way to delete a dataset: metadata and stored files could only ever accumulate, never be removed

**Severity:** Medium

**Area:** Backend / Storage

**Status:** FIXED

*(Found during a storage-architecture review, Step 1: "identify dataset
deletion logic" — there wasn't any. Not a regression; this capability
never existed since Phase 2.)*

### Description

There was no `DELETE` endpoint for datasets, no `delete()` method on
`DatasetRepository`, and no code path that ever called
`StorageProvider.delete()` for a dataset's file. Every uploaded file —
local disk or (eventually) R2 — was permanent by omission: the only way
to remove one was to reach into the database and filesystem by hand.

### Steps to Reproduce

Code review: `grep -rn "def delete" app/repositories/dataset_repository.py`
returned nothing; `app/api/v1/datasets.py` had no `DELETE` route.

### Expected Behavior

A user can delete a dataset they own; both the DB row and the underlying
stored file are removed, along with anything that referenced it.

### Actual Behavior

No such capability existed at any layer.

### Root Cause

Never built — Phase 2 shipped upload/list/get/query but not delete.

### Proposed Fix

Add `DatasetRepository.delete()`, `DatasetService.delete_owned()` (verifies
ownership, deletes the DB row *then* the storage object — see BUG-007's
note on ordering), and `DELETE /api/v1/datasets/{id}`. `Insight` and
`DashboardChart` already had `ondelete="CASCADE"` foreign keys to
`datasets.id` from Phases 4/5, so deleting the DB row automatically takes
any insights/dashboard charts referencing that dataset with it — no
additional cascade logic needed there.

### Regression Risk

Low — purely additive (a new method + a new route); nothing existing calls
or depends on dataset deletion not existing.

### Fix Applied

See above. Also wired up on the frontend: a delete button on each dataset
row (`datasets-page.tsx`), calling the new endpoint via a `useDeleteDataset`
hook.

### Verification

Verified live end-to-end (not just pytest): uploaded a CSV, confirmed its
file existed on disk, created an insight and a dashboard chart referencing
it, then deleted the dataset — confirmed via direct API calls that: the
dataset now 404s, the file is actually gone from disk (`find` for it
returns nothing), the insight list is empty, and the dashboard's chart
list is empty (cascade held). A second, unrelated XLSX dataset for the
same user was confirmed still present and untouched throughout. Also
covered by 4 new pytest cases (delete + auth + cross-tenant 404 + cascade)
and re-run as part of the full 48-test suite.

---

## BUG-007 — Orphaned file left on disk if the database write fails after the file was already saved

**Severity:** Medium

**Area:** Backend / Storage / Data integrity

**Status:** FIXED

*(Found during the same storage-architecture review, Step 3: "clean up
partially written files when uploads fail." Latent since Phase 2 — never
triggered in prior testing because nothing had exercised a mid-upload DB
failure specifically.)*

### Description

`DatasetService.upload()` called `storage.save(key, data)` and then
`repo.create(...)` with nothing in between to undo the save if the DB
insert raised. A transient DB error (a dropped connection, a constraint
violation, anything) after a successful `storage.save()` would leave a
file on disk with no database row ever pointing to it — permanently,
since nothing else references it to ever clean it up.

### Steps to Reproduce

Monkeypatch `DatasetRepository.create` to raise, then call
`DatasetService.upload(...)`: before the fix, the file written by
`storage.save()` remained on disk after the exception propagated.

### Expected Behavior

A failed upload should leave no trace — no orphaned file, no orphaned
metadata.

### Actual Behavior

The file survived the failed upload with nothing tracking it.

### Root Cause

No `try/except` around the `repo.create()` call to undo the preceding
`storage.save()` on failure.

### Proposed Fix

Wrap `repo.create()` in a `try/except`; on any exception, call
`storage.delete(storage_key)` to remove the just-saved file, log it, and
re-raise the original exception.

### Regression Risk

None on the success path — the new `try/except` only does anything when
`repo.create()` raises, which it already didn't do in any passing test.

### Fix Applied

`app/services/dataset_service.py`: `repo.create(...)` now runs inside a
`try/except Exception`, calling `self._storage.delete(storage_key)` and
logging `dataset_create_failed_cleaning_up_storage` before re-raising.

### Verification

New pytest case `test_upload_cleans_up_the_file_if_the_db_write_fails`:
monkeypatches `DatasetRepository.create` to raise `RuntimeError`, calls
`DatasetService.upload()` directly, and asserts (a) the exception still
propagates (callers still see the failure) and (b) no file exists under
the storage root afterward. Exercised at the service layer rather than
over HTTP — a raw exception escaping through Starlette's
`BaseHTTPMiddleware` (our request-logging middleware, added in Phase 6)
hits a known `TestClient`/anyio task-group interaction unrelated to this
fix; the cleanup logic itself is what's under test, and the log line
(`dataset_create_failed_cleaning_up_storage`) was also observed firing
correctly in a full-suite run before the test was adjusted to assert
against the service layer directly.

---

## BUG-CI-001 — Backend CI failing (`CI / Backend (lint, typecheck, test)`)

**Severity:** High

**Area:** CI / Backend / Tooling

**Status:** FIXED

### Description

The backend CI job was failing while frontend CI passed. Reproduced by
cloning the pushed repo into a fresh directory, building a fresh Python
3.12 venv, and running the exact four commands the workflow runs, with
the exact same job-level environment variables (`DATABASE_URL`,
`ENVIRONMENT=test`, `SECRET_KEY=ci-only-secret-not-for-real-use`) and
**no manually-exported `PYTHONPATH`** — which is precisely what I'd been
doing locally, out of habit, every single time I ran these commands
throughout this project, without ever noticing the actual `ci.yml` never
sets it. That gap between "what I verified locally" and "what CI actually
runs" is what let all of the below go unnoticed until now.

Four independent, stacked causes — fixing the first would only have
exposed the next:

**1. `ruff check .` — 26 pre-existing lint errors, all in `alembic/`.**
Every previous local check this project ran was scoped to `ruff check app`
or `ruff check app tests` — never the `.` (whole `backend/` directory)
that CI's workflow actually runs — so lint debt in `alembic/env.py` and
every migration file (unsorted imports, `typing.Sequence`/`Union` instead
of `collections.abc.Sequence`/`X | Y`) was never actually checked, let
alone fixed.
*Fix:* `ruff check --fix .` — 31 fixes, entirely mechanical import
modernization, zero semantic change (confirmed via diff review).

**2. `mypy app` — 1 real type error in `app/core/logging.py`.** This had
been carried as an accepted "pre-existing cosmetic nit" across every prior
phase of this project — but `mypy` exits non-zero on any error, so it was
silently failing CI's typecheck step the whole time. Root cause:
`_redact_sensitive`'s hand-written signature (`_logger: object`,
`event_dict: dict`, return `dict`) didn't structurally match structlog's
own `Processor` type alias.
*Fix:* typed it against structlog's own exported aliases
(`structlog.typing.WrappedLogger`, `structlog.typing.EventDict`) instead
of approximating the signature by hand — the correct fix, not a
`# type: ignore`.

**3. `pytest` — `ModuleNotFoundError: No module named 'app'`.** `tests/`
has no `__init__.py`, so pytest's own rootdir-insertion adds `tests/` to
`sys.path`, not `backend/` (where `app/` actually lives). Every previous
local test run this project ran manually exported `PYTHONPATH=.` first;
the CI workflow never has, and never needed to if the project itself were
configured correctly. (Note: `alembic upgrade head` was never affected —
`alembic.ini` already has `prepend_sys_path = .`, which is alembic's own
equivalent mechanism; I'd mistakenly attributed my habitual `PYTHONPATH=.`
exports to alembic too, when it was only ever pytest that needed it.)
*Fix:* added `pythonpath = ["."]` to `[tool.pytest.ini_options]` in
`backend/pyproject.toml` — pytest's own first-class, official mechanism
for exactly this layout, so it works identically for anyone (local, CI,
or a future contributor) with zero required environment ceremony. Not a
CI-only patch to the workflow's `env:` block, which would only have fixed
it for CI specifically.

**4. `test_config.py::test_development_allows_the_default_secret_key`
— a real test hermeticity bug.** The test asserts that `Settings()`
falls back to its hardcoded default `SECRET_KEY` — but never isolates
itself from the ambient environment. CI's job-level `env:` sets a real
`SECRET_KEY` for every step in the job (including this test), and
pydantic-settings reads real environment variables ahead of a field's
class-level default for any field not passed explicitly to the
constructor — so the test asserted a default that the environment was
actively overriding, and failed. The other three tests in the same file
were unaffected because each passes every relevant field explicitly.
*Fix:* `monkeypatch.delenv("SECRET_KEY", raising=False)` before
constructing `Settings` — makes the test's own isolation explicit and
correct, rather than relying on nobody's shell happening to have that
variable set.

### Steps to Reproduce

1. Clone the repo fresh into an empty directory (isolates from any local
   `.venv`, `__pycache__`, or exported shell state).
2. Build a fresh Python 3.12 venv, `pip install -r requirements-dev.txt`.
3. Start a real Postgres matching the workflow's `services.postgres`
   config (`pulseiq`/`pulseiq`/`pulseiq`).
4. Export exactly `DATABASE_URL`, `ENVIRONMENT=test`,
   `SECRET_KEY=ci-only-secret-not-for-real-use` — nothing else.
5. Run, in order: `ruff check .`, `mypy app`, `alembic upgrade head`,
   `pytest` — each one reproduced its failure exactly as described above.

### Root Cause

Summarized above per stage — in one sentence: local verification
throughout this project always used a narrower/more-forgiving command or
environment than what the actual CI workflow runs, so four real (if
mostly small) defects accumulated without ever being caught.

### Proposed Fix

See the four fixes above — each addresses its actual root cause; none
disables, skips, or suppresses a check.

### Regression Risk

Very low. Three of the four changes are mechanical/additive (lint auto-
fix, a type annotation matching the library's own contract, a test
isolating itself with `monkeypatch`); the `pythonpath` addition only
affects how `app` is discovered during test collection, not runtime
behavior.

### Fix Applied

`backend/alembic/env.py` + all 5 `backend/alembic/versions/*.py` (ruff
`--fix`), `backend/app/core/logging.py` (typed against structlog's own
aliases), `backend/pyproject.toml` (`pythonpath = ["."]`),
`backend/tests/test_config.py` (`monkeypatch.delenv`).

### Verification

- Lint: PASS (`ruff check .` — 0 errors, was 26)
- Typecheck: PASS (`mypy app` — 0 errors, was 1)
- Tests: PASS (48/48, was 47/48)
- All four re-verified twice: once in a fresh, isolated clone (to
  confirm the fix works with zero dependency on this session's
  accumulated local state), and again in the actual project directory.
- Frontend CI: untouched, no changes made there.
- **Honest limitation:** this file records verification of the exact
  commands and environment the workflow runs, reproduced locally and in
  an isolated fresh clone — not a completed GitHub Actions run, since
  that only resolves once these changes are actually pushed. Don't take
  "backend CI passing" as confirmed until the next real workflow run
  shows it.

---

## BUG-009 — Frontend container couldn't run standalone at all: nginx refused to start outside Docker Compose's own network

**Severity:** High

**Area:** Infrastructure / Docker / Deployment

**Status:** FIXED

*(Found while preparing to deploy the frontend and backend as two
separate Railway services — this container had only ever been run via
`docker-compose.yml`, which supplies a Docker network where the hostname
`backend` resolves. Nothing before this had run the frontend image any
other way.)*

### Description

`nginx.conf`'s `location /api/ { proxy_pass http://backend:8000/api/; }`
resolves the hostname `backend` **eagerly, when nginx loads its config at
startup** — not lazily per-request. That hostname only exists inside
Compose's own Docker network. Run the exact same image standalone (a
plain `docker run`, or as its own Railway service with no Compose network
present), and nginx fails to even start.

### Steps to Reproduce

```
docker run --rm -p 8080:80 <frontend-image>
```
→ `nginx: [emerg] host not found in upstream "backend" in
/etc/nginx/conf.d/default.conf:14` — the container exits immediately.

### Expected Behavior

The same image should be able to run as its own standalone service (no
Compose network needed) — necessary the moment frontend and backend are
deployed to two separate platforms/services, which was always the plan
for R2/production per `docs/DEPLOYMENT.md`.

### Actual Behavior

Hard startup crash, not a soft failure — the container never reaches a
running state at all.

### Root Cause

`proxy_pass` with a literal (non-variable) URL resolves its hostname at
config-load time. `backend` is only a real hostname inside Compose's
network; nothing told nginx it was allowed to not-yet-know that address
until an actual request needed it.

### Proposed Fix

Give nginx its own resolver (Docker's embedded DNS, `127.0.0.11`) and
reference the upstream through an nginx variable rather than a literal
string — this defers resolution to request time, so config loading (and
thus container startup) never depends on `backend` being resolvable at
all. (See BUG-010 for a second, related bug this same change initially
introduced.)

### Regression Risk

Low — only affects how/when the `/api/` proxy resolves its target;
doesn't change any other route, and the location block is unreachable
anyway whenever `VITE_API_URL` is set at build time (the split-host case
this fix exists for), since the frontend's own JS calls the real backend
origin directly rather than this container's `/api/` path.

### Fix Applied

`frontend/nginx.conf.template`: added `resolver 127.0.0.11 valid=10s;`
and rewrote the proxy target as `set $backend_upstream http://backend:8000; proxy_pass $backend_upstream;`.

### Verification

- `docker run --rm -p 8080:80 <image>` (no Compose network) — nginx now
  starts and serves `200` on `/`, confirmed live.
- `docker compose up` — both containers still healthy, unchanged
  behavior for the topology this was originally built for.

---

## BUG-010 — The fix for BUG-009 introduced a path-duplication bug: `/api/` proxied requests 404'd (`/api//api/v1/...`)

**Severity:** High

**Area:** Infrastructure / Docker

**Status:** FIXED

*(Found immediately after applying BUG-009's fix, by actually testing a
real request through it rather than only checking that nginx started.)*

### Description

nginx's `proxy_pass` has a documented behavior change once its target
includes a *variable*: with a literal URL, nginx rewrites the matched
`location` prefix into whatever URI follows the target in `proxy_pass`
(so `location /api/ { proxy_pass http://x/api/; }` maps `/api/v1/login` →
`http://x/api/v1/login`, correctly). With a variable in play, nginx can
no longer do that rewrite at config-load time — it passes the entire
original request URI through unchanged, appended after the variable.
BUG-009's fix kept a `/api/` suffix after the variable
(`proxy_pass $backend_upstream/api/;`), which — with a variable
involved — doesn't get treated as a rewrite target at all; it's just
concatenated in front of the (already `/api/`-prefixed) original request
URI, duplicating it.

### Steps to Reproduce

With BUG-009's fix applied as first written, through the full
docker-compose stack: `POST /api/v1/auth/login` via the frontend's nginx
proxy.

### Expected Behavior

`200`/`401` (a real auth response) — the request should reach
`http://backend:8000/api/v1/auth/login`.

### Actual Behavior

`404 {"detail":"Not Found"}` — a real FastAPI 404 (confirmed via nginx's
access log: the request *did* reach the backend container; the body is
Starlette's own default-404 shape, not nginx's). The actual upstream URL
nginx constructed was `http://backend:8000/api//api/v1/auth/login` — a
duplicated `/api/` segment FastAPI has no route for.

### Root Cause

Explained above: a URI written after a variable in `proxy_pass` is not a
rewrite target, it's a literal prefix — concatenated in front of the full
original request URI, not replacing any part of it.

### Proposed Fix

Drop the URI entirely from `proxy_pass` when a variable is involved —
`proxy_pass $backend_upstream;` with nothing after it — so nginx passes
the complete, correct, un-duplicated original request URI straight
through.

### Regression Risk

None beyond what BUG-009 already carries — this is a same-day, same-block
correction before it was ever committed/deployed anywhere.

### Fix Applied

`frontend/nginx.conf.template`: `proxy_pass $backend_upstream/api/;` →
`proxy_pass $backend_upstream;`.

### Verification

Full round trip through the actual nginx proxy, live: `GET
/api/v1/health` → `200`; `POST /api/v1/auth/signup` → `201` with real
tokens; `GET /api/v1/auth/me` with the returned token → `200` with the
correct user. Re-confirmed the standalone (no-Compose) case from BUG-009
still starts and serves correctly after this second change too.

---

## BUG-011 — Frontend Dockerfile had no way to receive `VITE_API_URL`, and was hardcoded to port 80 (PaaS hosts inject a dynamic `$PORT`)

**Severity:** Medium

**Area:** Infrastructure / Docker / Deployment

**Status:** FIXED

*(Found while preparing to deploy the frontend as its own Railway
service, alongside BUG-009/010 — the same underlying cause: this image
had only ever been built/run through `docker-compose.yml`, which never
needed either.)*

### Description

Two related gaps, both invisible under Docker Compose specifically:

1. Vite only reads `VITE_*` variables **at build time**, baking them into
   the static JS — there's no such thing as a "runtime env var" for an
   already-built bundle. The Dockerfile's build stage had no `ARG`/`ENV`
   to receive `VITE_API_URL` at all, so a split-host deployment (frontend
   and backend as separate services on different domains — exactly the
   Railway plan) would silently bake in the fallback relative `/api/v1`
   path instead, which only resolves correctly behind this container's
   own nginx proxy — never against a separate backend service's domain.
2. nginx's config had a hardcoded `listen 80;` and the `HEALTHCHECK`
   hit a hardcoded port 80 — most PaaS hosts (Railway included) inject a
   dynamic `PORT` and expect the container to bind to it, exactly the
   same class of bug as BUG-001/the backend's own Dockerfile fix earlier
   in this file.

### Steps to Reproduce

1. `docker build --build-arg VITE_API_URL=https://example.com/api/v1 .`
   then inspect the built JS bundle — before the fix, the string never
   appears there at all; the build had no mechanism to receive it.
2. `docker run -e PORT=9700 ...` — before the fix, nginx still listens on
   80 regardless, ignoring the injected port entirely.

### Expected Behavior

The image should bake in a real backend URL when given one, and bind to
whatever port the platform tells it to.

### Actual Behavior

Neither happened — both silently ignored.

### Root Cause

Never built — this Dockerfile predates any split-host deployment plan;
Docker Compose's shared network made both gaps invisible.

### Proposed Fix

Declare `ARG VITE_API_URL` + `ENV VITE_API_URL=$VITE_API_URL` before the
build step (so `docker build --build-arg` works, and any platform that
passes build args through a Dockerfile build gets it too). Convert
`nginx.conf` into `nginx.conf.template`, using nginx's own official
`envsubst`-on-templates entrypoint mechanism to substitute `${PORT}` at
container start, with `ENV PORT=80` as the default for plain
`docker run`/Compose, where nothing else sets it.

### Regression Risk

Low — purely additive (a new build ARG, a template mechanism that
produces identical output — verified — when `PORT` is unset/80).

### Fix Applied

`frontend/Dockerfile`: added the `ARG`/`ENV` pair before `RUN npm run
build`; `nginx.conf` → `nginx.conf.template`, copied to
`/etc/nginx/templates/default.conf.template` instead of directly to
`conf.d`; `ENV PORT=80` default; `HEALTHCHECK` made shell-form to expand
`${PORT}`.

### Verification

- `docker build --build-arg VITE_API_URL=https://fake-backend.example.com/api/v1 .` then `docker run -e PORT=9700 -p 9700:9700 <image>`:
  responded `200` on port **9700** (not 80), and the built JS bundle
  (`grep`-confirmed) contains `fake-backend.example.com/api/v1` literally.
- Default build/run (no `PORT`, no `VITE_API_URL` — the docker-compose
  case): unchanged, `listen 80`, relative `/api/` behavior preserved,
  regression-checked directly.

## BUG-012 — Railway backend deployment failed: `dockerfilePath` set relative to the repo root instead of the service's `rootDirectory`, so Railway never used the Dockerfile at all

**Severity:** High

**Area:** Infrastructure / Deployment (Railway)

**Status:** FIXED

### Description

The Railway backend service (`PULSEIQ`, project `PulseIQ`) had
`source.rootDirectory = "backend"` and `build.dockerfilePath =
"backend/Dockerfile"` set via the Railway API. Every deploy still used
Railway's Railpack auto-detection builder instead of the Dockerfile,
which detected Python via `pip` and failed with `No start command
detected` before a container ever ran. This is what GitHub reported as
the failing `PulseIQ - PULSEIQ — Deployment` check. A second, unrelated
Railway project (`joyful-quietude`, created earlier while trying
different "New Project from GitHub repo" attempts) has its own `PULSEIQ`
service pointed at the same repo with no root directory or Dockerfile
config at all, and fails the same way — reported as the
`joyful-quietude - PULSEIQ — Deployment` check. Both checks share the
same underlying class of cause (Railway never switching to a Docker
build) but are two independent service configs, not one shared bug.

### Steps to Reproduce

1. `railway status --json` on the `PULSEIQ` service showed the latest
   deployment's frozen `serviceManifest` with `builder: "RAILPACK"`,
   `rootDirectory: null`, `dockerfilePath: null` — i.e. whatever config
   had been set previously was never actually picked up by a real
   deploy.
2. `railway logs --service PULSEIQ --build --json` on that deployment
   showed Railpack's own log output: `Detected Python`, `Using pip`,
   `✖ No start command detected`, then the build process exiting 1.
3. `railway environment config --json` showed the *currently configured*
   (not yet re-deployed) values: `build.builder = "DOCKERFILE"`,
   `build.dockerfilePath = "backend/Dockerfile"`, `source.rootDirectory =
   "backend"` — this is the actual root cause: with `rootDirectory`
   already scoping the build context to `backend/`, `dockerfilePath` is
   resolved *relative to that root*, so the correct value is `Dockerfile`
   — `backend/Dockerfile` resolves to a nonexistent
   `backend/backend/Dockerfile`, and Railway silently falls back to
   Railpack auto-detection rather than erroring loudly about the missing
   path.

### Expected Behavior

With a Dockerfile present in the service's root directory, Railway
should build from it and run the app inside the container, honoring the
Dockerfile's own `CMD` (migrations + `uvicorn` bound to `$PORT`) and the
configured `healthcheckPath`.

### Actual Behavior

Railway silently ignored the Dockerfile and fell back to Railpack's
Python auto-detection, which has no way to know this project starts via
`uvicorn` inside a container, and failed outright.

### Root Cause

`build.dockerfilePath` was set as a full repo-relative path
(`"backend/Dockerfile"`) while `source.rootDirectory` (`"backend"`) had
already scoped the build context — the two fields compose (path is
resolved inside the root directory, not from the repo root), so the
effective path Railway looked for did not exist. Confirmed by setting
`dockerfilePath` to `"Dockerfile"` (relative to the already-set
`rootDirectory`) via a JSON `environment edit` patch and observing the
very next deployment's build logs actually invoke the Dockerfile build
stages instead of Railpack.

### Proposed Fix

Set `build.dockerfilePath = "Dockerfile"` (not `"backend/Dockerfile"`)
on the `PULSEIQ` service, given `rootDirectory` is already `"backend"`.
No application code changes required — this was a platform
configuration value only.

### Regression Risk

None — no code changed; this only corrects a Railway service config
field.

### Fix Applied

Ran `railway environment edit --json` with a patch setting
`services.<serviceId>.build = {"builder": "DOCKERFILE", "dockerfilePath":
"Dockerfile"}` and `source = {"rootDirectory": "backend"}` on the
`PULSEIQ` service in the `PulseIQ` project, then `railway redeploy
--from-source`. `docs/DEPLOYMENT.md` step 2 (backend setup) updated to
call out this exact gotcha explicitly, so re-creating the service later
doesn't repeat the mistake.

### Verification

- `railway deployment list --service PULSEIQ --json` on the new
  deployment showed `serviceManifest.build.builder = "DOCKERFILE"` and
  `dockerfilePath = "Dockerfile"` actually baked into that deployment
  (not just the pending config) — the build logs for it show real
  Docker build stages (`npm ci`/`pip install`-equivalent steps for this
  Dockerfile), not Railpack's Python auto-detection banner.
- The deployment reached `SUCCESS` (polled via `railway deployment list
  --json` until a terminal status, not assumed from a queued state).
- `curl https://pulseiq-production-0585.up.railway.app/api/v1/health`
  returned `200` with body `{"status":"ok","storage_provider":"local"}` —
  a real HTTP request against the live Railway deployment, not a local
  simulation.
- The stray `joyful-quietude` project — confirmed via `railway api` query
  to be a duplicate/orphaned project from an earlier failed "New
  Project" attempt (same repo, no `rootDirectory`, no unique purpose,
  not part of the intended one-project/two-services architecture) — was
  presented to the account owner, who chose deletion. Deleted via
  `railway api` (`projectDelete`), confirmed gone from `railway project
  list`. Its failing `joyful-quietude - PULSEIQ` check will no longer
  appear on future commits.

---

# Final QA Summary

## Total Issues Found

12

## Fixed

12 (BUG-001 Critical, BUG-002 Medium, BUG-003 High, BUG-004 Medium,
BUG-005 Medium — found while actually getting Docker running, in a
follow-up session after the rest of this file was first written —
BUG-006 Medium and BUG-007 Medium — found during a dedicated storage-
architecture review in a further follow-up session — BUG-CI-001 High —
found while diagnosing a real, reported backend CI failure in a further
follow-up session — BUG-009 High, BUG-010 High, BUG-011 Medium — found
while actually deploying, when the frontend was run standalone/on Railway
for the first time ever, in a further follow-up session — BUG-012 High —
found while diagnosing a real, reported Railway deployment failure in a
further follow-up session. (BUG-008 is not missing — it was never
allocated to a shipped fix; skipping straight to 009 rather than
renumbering everything above it.))

## Remaining

0 logged bugs. Several genuine, un-fixed limitations remain — see below,
not hidden.

## Testing methodology and honesty note

This environment has **no browser-automation tool** (no Playwright/
Puppeteer/screenshot capability) and **no frontend test runner is
configured in the repo** (no Vitest/Jest/Playwright config exists — this
predates this QA pass, it's a pre-existing gap, not something newly
discovered and then ignored). Given that:

- **Backend, API, database, AI pipeline, and security findings** above are
  from actually running the app against a **real external Postgres (Neon)**
  and a **real Groq API call** (using the user's own key) — issuing real
  HTTP requests and reading real responses, not just reading code. This
  includes the full primary user journey (signup → login → upload CSV →
  upload XLSX → verify storage on disk → inspect profiling → ask AI → save
  insight → create dashboard + chart → simulated "refresh" via a fresh
  authenticated call → confirm protected routes reject no-token requests),
  run twice (once mid-testing, once as a final regression after all fixes).
- **Frontend findings** are from careful code review of every page and
  component (all written this session) plus `tsc`/`oxlint`/`npm run build`
  — genuinely run, not just read — but I could not click through the UI,
  observe rendered charts, or check responsive layout at different
  viewport sizes myself. Anything frontend-related above is labeled as
  code review, not interactive testing, and that distinction is real.
- I did not fabricate issues to pad this report. Several test categories
  in the original QA brief (SQL injection, DuckDB query behavior) don't
  apply to this codebase's actual architecture (see the architecture note
  at the top of this file) and are reported as such rather than forced
  into a finding that doesn't exist.

## Remaining Known Limitations (genuine, not hidden)

- **No frontend automated tests** (no Vitest/Jest/Playwright/RTL
  configured). Everything frontend-side has been verified by `tsc`,
  `oxlint`, successful builds, and careful manual code review across every
  phase this session, but there's no regression safety net for future UI
  changes the way the backend has (34 pytest cases).
- **Legacy `.xls` is accepted at upload but cannot be profiled or queried**
  — `openpyxl` doesn't read the old binary Excel format, and no dependency
  for it (e.g. `xlrd`) is installed. Datasets uploaded as `.xls` land in
  `status="profiling_failed"` by design, not silently — but the capability
  gap itself is real and was a known, accepted scope limit from Phase 3,
  not something this QA pass introduced.
- **Cloudflare R2 storage is implemented but genuinely untested against a
  real R2 bucket** — no R2 credentials were available in this session.
  What *was* verified: misconfigured R2 (provider selected, credentials
  missing) fails cleanly with a generic 500 and a clear server-side log,
  without crashing the process or leaking internals to the client.
- **No background job queue** — dataset profiling and AI `/ask` calls run
  synchronously in the request. This was a deliberate, discussed decision
  in Phase 6 (the user chose to defer it), not an oversight, but it means
  a very large file or a slow LLM response ties up a request thread for
  its full duration.
- **No deployment target configured** — also a deliberate Phase 6
  deferral. The app has been run and tested locally (native processes)
  and against a real external Neon database, but never deployed to a
  hosting platform.
- **The AI's generated queries and answers are still a live LLM** — even
  with the BUG-003 fix, responses are not byte-identical across runs.
  Behavior was verified by re-running the same prompts multiple times and
  confirming consistent *behavior* (refusal on mutation attempts, correct
  numbers on real questions), not by asserting exact string output — which
  is the right level of testing for a non-deterministic model, but worth
  naming explicitly as a different kind of guarantee than the
  deterministic backend logic.
- **One pre-existing, cosmetic mypy finding remains untouched**:
  `app/core/logging.py:31` — a third-party (`structlog`) callable
  signature mypy considers slightly incompatible with its own stub types.
  This predates every phase built this session, has no runtime effect
  (confirmed — logging works correctly throughout every test above), and
  was intentionally left alone each time it was reviewed rather than
  papered over with a type-ignore, so it's noted here rather than hidden.

## Core Feature Status

Authentication: **PASS**
Dataset Upload: **PASS**
Cloud Storage: **PASS (local disk, including full delete/cleanup lifecycle
— BUG-006/007 fixed)** / **UNTESTED (R2 — no credentials available;
misconfiguration failure mode verified clean; interface now carries
`exists()`/`local_path()` alongside `save/open/delete` so R2 needs no
interface changes to adopt, only real credentials — see STORAGE.md)**
Dataset Profiling: **PASS** (after BUG-002 fix)
Analytics Engine: **PASS**
AI Analytics: **PASS** (after BUG-003 fix)
SQL Safety: **N/A — no SQL exists in this codebase** (see architecture
note); the analogous structured-query safety surface was tested and
passes (injection-style filter values treated as inert data, unknown
columns rejected, cross-tenant access blocked)
Visualization: **PASS (code review + build only — bar/line charts via
ECharts, not interactively viewed; no pie/donut by design)**
Saved Analysis (Insights): **PASS**
Dashboard: **PASS**
Security Review: **PASS** — direct prompt injection refused, data-embedded
prompt injection quoted-but-refused, no SQL/mutation surface to inject
into, cross-tenant isolation holds across datasets/insights/dashboards/
charts, no secrets or stack traces leaked in any error response, no XSS
surface in the frontend (no `dangerouslySetInnerHTML` anywhere)
Regression Testing: **PASS** — 34/34 backend tests, full primary user
journey re-run end-to-end after all fixes, `ruff`/`mypy`/`tsc`/`oxlint`/
frontend build all clean
Docker Deployment: **PASS** (after BUG-005 fix) — `docker compose up`
brings up backend + frontend cleanly, both report `healthy`, migrations
run against the real external database on container start, and the full
primary journey (signup → login) was re-verified through the
containerized nginx `/api` proxy, not just natively. `docker-compose.yml`
no longer runs a separate local Postgres container — both Docker and
native runs now use the same `DATABASE_URL` (Neon), one database instead
of two to keep in sync.
