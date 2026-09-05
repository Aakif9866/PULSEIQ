# Security

The actual security model implemented, and its known limitations, stated
plainly. **This is not a claim of enterprise security or a completed
audit** — it's an honest account of what exists today.

## Authentication

JWT (HS256), issued as an access token (24h) and refresh token (14d) on
signup/login. Passwords hashed with bcrypt via `passlib`. `SECRET_KEY`
signs every token; `app/core/config.py` has a hard startup guard —
`Settings` **refuses to even construct** if `ENVIRONMENT=production` and
`SECRET_KEY` is still the insecure placeholder, or if `DEBUG=true` in that
environment. Verified live: importing the app with those settings raises
immediately, before anything else runs.

## Protected routes & user resource isolation

Every route that touches a user's data requires a valid bearer token
(`get_current_user`, a FastAPI dependency). Every dataset/insight/
dashboard/dashboard-chart lookup is scoped to `owner_id = current_user.id`
at the repository layer — there is no query anywhere that can return
another user's row.

**Verified directly, not assumed:** attempting to read, query, delete, or
attach a chart to another user's dataset/dashboard/insight returns `404`,
not `403` — deliberately, so a user can't even confirm a resource exists
under someone else's account. Covered by dedicated cross-tenant tests for
every resource type (see `docs/TESTING.md`).

## File upload validation

- **Extension allowlist**: only `.csv`, `.xlsx`, `.xls` accepted
  (`ALLOWED_UPLOAD_EXTENSIONS`); anything else is rejected before the file
  touches storage.
- **Size limit**: `MAX_UPLOAD_SIZE_MB` (default 200), enforced before any
  database or storage write — a rejected upload leaves no trace.
- **Content is validated by actually trying to profile it.** A file with
  the right extension but garbage/corrupted content (verified with random
  bytes named `.xlsx`) fails profiling cleanly (`status=profiling_failed`)
  rather than crashing the request.

## Path traversal prevention

Storage keys are **never** derived from a client-supplied filename — a key
is always `{owner_id}/{a fresh server-generated uuid4}{extension}`; the
original filename is kept only as display metadata in Postgres, never
used to build a path. `LocalStorageProvider` additionally resolves every
path and verifies it stays under the configured storage root before
touching disk — a key containing `../` is rejected outright
(`ValueError: Storage key escapes storage root`), verified directly.

## Query safety (in place of "SQL validation")

There is no SQL anywhere in this codebase (see `ARCHITECTURE.md`) — so
there's no SQL injection surface to validate against. The actual analogous
control: every analytical query (hand-built or AI-generated) is a closed
Pydantic schema (`DatasetQueryRequest`) with a fixed set of operations
(group_by/aggregate/filter/sort/limit); every column name referenced is
checked against the dataset's real schema before execution, and an
injection-style string passed as a filter *value* (tested with
`'; DROP TABLE users; --`) is treated as inert literal data — there's
nothing for it to break out into.

## Restricted analytical query execution

- **Row cap always enforced** (`QUERY_ROW_LIMIT`), regardless of what a
  query requests.
- **Wall-clock timeout** (`QUERY_TIMEOUT_SECONDS`) bounds how long the
  caller waits — an **HTTP-level guard**, not a true compute-kill switch
  (Python can't forcibly cancel a running native Polars call; a real one
  needs an out-of-process worker, not yet built).
- Applies identically whether the query came from a human or the AI
  analyst — no privileged path for either.

## Environment variable & secret management

- `.env` is git-ignored; `.env.example` (committed) documents every
  variable with no real values.
- Settings are read once via `pydantic-settings` (`app/core/config.py`);
  nothing storage-, database-, or AI-related is hardcoded elsewhere.
- Structured logs (`structlog`) run every event through a redaction filter
  that replaces `password`/`token`/`access_token`/`refresh_token`/
  `api_key`/`secret` keys with `***redacted***` before they're ever
  written — verified this predates and continued through every phase of
  this project.
- The R2 misconfiguration error names *which* environment variables are
  missing, never their values.

## CORS

`CORS_ORIGINS` defaults to `http://localhost:5173`/`:3000` only — no
wildcard origin. Must be set explicitly for any real deployed frontend
origin.

## Known limitations (not hidden)

- **No rate limiting anywhere** — not on login attempts, not on AI calls,
  not on uploads. A determined caller could brute-force a password or
  run up a Groq bill. Would be a prerequisite for any public deployment.
- **Refresh tokens are persisted in the frontend's `localStorage`** (via
  Zustand's `persist` middleware), not an `httpOnly` cookie — a
  pragmatic, documented trade-off for this project's current scope, not
  the stricter option. Vulnerable to token theft via XSS if one were ever
  introduced (none is currently known — no `dangerouslySetInnerHTML`
  anywhere in the frontend, verified by direct search).
- **No account lockout, no CAPTCHA, no email verification** on signup.
- **No audit log** of who accessed what, beyond the structured request
  logs (which carry a `request_id` but aren't a security audit trail).
- **R2 credentials, if ever configured, are read into a boto3 client at
  process start** — standard practice, but there's no secrets-manager
  integration (Vault, AWS Secrets Manager, etc.); `.env` is the only
  secret store today.
- **Cloudflare R2 storage is unverified against a real bucket** (see
  `docs/STORAGE.md`) — the misconfiguration failure path is verified, a
  real credential round trip is not.
