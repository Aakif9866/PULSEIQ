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

## Phase 7 — V2: Hybrid AI Analyst, History & Data Quality (built, feature branch)

Built on `feature/pulseiq-v2-roadmap`, not merged to `main`/deployed. Full
detail: [V2_ROADMAP.md](V2_ROADMAP.md), [AI_ANALYTICS.md](AI_ANALYTICS.md).

- [x] Hybrid AI Analyst engine (`app/ai/analyst_engine.py`) — a tool-calling
      loop over 16 deterministic tools (dataset profile, column stats,
      missing values, duplicates, outlier detection, logical-violation
      rules, correlation, time series, group/filter/formula validation,
      top/bottom records); every number in an answer traces back to a real
      tool call, never an LLM guess. `POST /datasets/{id}/analyze`.
- [x] Answer validator (`app/ai/answer_validator.py`) — cross-checks every
      finding's numbers against actual tool-call evidence before marking it
      verified; downgrades confidence and flags (never silently drops) a
      finding that can't be matched to real evidence.
- [x] Provider reliability layer (`app/ai/providers/groq_provider.py`) —
      retry/backoff on empty responses, and a salvage path for a
      live-discovered Groq quirk (model calls a fake `"json"` tool to
      express its final answer while `tools=` is still attached).
- [x] Query history & saved queries (`query_history`/`saved_queries`
      tables, migration `0007`) — every AI-answered or SQL-Explorer query
      logged; explicit named saves kept separate from the automatic log.
- [x] Natural Language to SQL (`app/ai/sql_generator.py`,
      `app/analytics/sql_engine.py`, `sql_validator.py`) — DuckDB execution
      behind a dedicated SQL validation layer (statement/table/column
      allow-list, forced row limit). `POST /datasets/{id}/ask-sql`.
- [x] SQL Explorer (`POST /datasets/{id}/sql`) — same validate/execute
      pipeline as NL-to-SQL, direct text-editor entry point; schema-derived
      suggested queries (no model call).
- [x] Dataset quality columns and richer profiling (migration `0008`,
      `app/analytics/data_profile.py`) — column kind inference, quantiles,
      duplicate-key detection, temporal spans, pairwise correlations,
      data-quality score.
- [x] Chart-type suggestion (`app/analytics/chart_suggestion.py`) — rule-
      based, not a model call.
- [x] 225 backend tests passing (ruff/mypy clean) covering all of the
      above, including a fake-in-process-provider engine test and a live
      Groq end-to-end run against all 16 tools.
- [x] `GET /history` 500 bug fixed — logging an `/analyze` call used a
      `source` value (`"ai_deep_analysis"`) the read schema's `Literal`
      didn't list yet; regression-tested.
- [ ] **Not yet done: none of this is wired into the frontend.** The "AI
      Analysis" page still calls the old, unvalidated `/ask` endpoint
      (`AnalystService.ask()` — one LLM call picks a query, one LLM call
      free-writes prose over the raw rows, no tool calls, no validation).
      This is the first item of Phase 8 below.

**Exit criteria:** met on the backend (a user can drive every feature above
through the real HTTP API with grounded, validated answers); not yet met
end-to-end through the UI.

## Phase 8 — V2 Completion & Portfolio Readiness (planned, not started)

Captured 2026-09-25 as a concrete, ordered plan for finishing Phase 7 and
taking it to a deployable, interview-defensible state. Nothing in this
phase has been built yet — recorded here so scope and ordering survive
between sessions. Ground rules for executing it (apply to every step
below): don't rewrite working systems, only extend them; run
pytest/ruff/mypy/`npm run typecheck`/`npm run lint` after each step and fix
failures before moving on; update this file and PROGRESS.md (and any other
affected doc) as part of each step's commit; one clean commit per step;
stop and ask before any breaking change, migration, new paid service, or
endpoint removal; never invent a metric — every number in docs or a resume
bullet must come from something actually measured; add a section to
`docs/LEARNING.md` per step (what was built, why this approach over the
alternatives, 3 interview questions to be ready for).

- [x] **Step 1 — Wire `/analyze` into the frontend.** AI Analysis page now
      calls `/analyze` by default (`AnalyzeAnalystView`), showing which
      tools ran, a per-finding verified/unverified indicator, the
      validator's confidence downgrade, and clear degraded/warning/
      tool-error banners. `/ask` kept fully working behind
      `VITE_AI_ANALYST_ENGINE=ask` (`AskAnalystView`, unchanged), marked
      deprecated in `docs/AI_ANALYTICS.md` — not deleted. Frontend test
      stack added from scratch (Vitest + Testing Library + jsdom — none
      existed before): 12 tests covering the empty state, a verified
      finding, an unverified finding shown-not-hidden, the degraded
      banner, a failed tool call surfaced, an API-error message, and
      conversation history sent on a follow-up question. Backend gained 2
      new regression tests proving a tool error and a `degraded` status
      both survive real HTTP JSON serialization
      (`test_analyze_surfaces_tool_error_and_degraded_status_over_http`),
      since the new UI reads those fields directly off the response.
      **Known gap, not worked around:** "Save insight"/"Add to dashboard"
      aren't wired up for `/analyze` answers yet — `InsightCreate`/
      `DashboardChartCreate` both require one `DatasetQueryRequest` +
      `row_count`, and `/analyze` can run several tool calls of different
      shapes (or none); faking a query from an arbitrary tool call would
      be misleading. Revisit once there's a real shape for "save this
      multi-tool analysis."
- [x] **Step 2 — NL-to-SQL safety audit.** Audited live against the real
      validator/engine (`app/analytics/sql_validator.py`,
      `sql_engine.py`), not a code read. **Two real, working bypasses
      found and fixed:** (1) bare function calls (`version()`,
      `current_database()`, `current_setting(...)`) were validated by
      neither the table nor the column check and executed successfully,
      disclosing engine/DB info — fixed by rejecting any `exp.Anonymous`
      function node (sqlglot maps every standard SQL function to its own
      class; everything else, including every DuckDB-specific function
      found, falls back to Anonymous — no hand-maintained allowlist
      needed); (2) a query specifying its own `LIMIT` (however large)
      bypassed the row cap entirely — fixed to always clamp to
      `min(requested, row_limit)`, treating a non-literal `LIMIT`
      expression as unbounded rather than trusted. Added
      `enable_external_access=false` on the DuckDB connection as a second,
      independent engine-level layer (verified live: doesn't break the
      registered dataset table; does independently block
      `read_csv`/`INSTALL` even with validation bypassed). Also closed a
      real test-coverage gap: the query-timeout guarantee had never
      actually been exercised by a test for the SQL path — added one
      proving a slow query surfaces a clean `408`, not a hang. Full
      write-up with every payload tried in `docs/SECURITY.md`. 18 new
      backend tests (245 total), ruff/mypy clean. Corrected a stale, now-
      false "there is no SQL/DuckDB anywhere in this codebase" claim in
      both `docs/ARCHITECTURE.md` and `docs/AI_ANALYTICS.md` — both
      predated V2's NL-to-SQL and were never updated after it shipped.
- [~] **Step 3 — Evaluation harness (built and verified; full live
      results run in progress, blocked partway by a real external
      limit).** `evals/` built: 51 questions across 2 deterministically-
      generated sample datasets, ground truth computed by calling
      `app.ai.tools` directly (never the LLM), covering all 16 tools,
      NL-to-SQL, and 4 multi-step questions; a runner that scores
      tool-selection accuracy, value accuracy, the validator's
      intervention rate, and real token/latency numbers pulled off
      Groq's own API response via an external instrumentation layer
      (`evals/instrumentation.py`, no production code changed for it).
      **Live run status**: 26/51 questions got a real, successful answer
      before Groq's free-tier *daily* token cap (200,000/day — separate
      from the per-minute limit already known about) was hit mid-run.
      Along the way, this run also found and fixed BUG-016 (an explicit
      `null` optional tool argument 400ing on Groq) and a real
      resilience gap in the runner itself — it only wrote results at the
      very end, so killing the process partway through the quota wall
      lost the 26 successful questions' detailed data (kept only as
      coarse pass/fail lines in the run log). Fixed: results are now
      written after every question, and `--resume` skips whatever
      already succeeded. Full numbered results are pending a completed
      run (resuming once quota allows) — `docs/EVALS.md` documents this
      status honestly rather than filling in estimated numbers.
- [x] **Step 4 — LLM rate limits and cost** (with stated gaps). Audited
      first: the model already never saw raw data (only column names/
      dtypes up front; tool results truncated at 4,000 chars; history and
      loop already capped). Added: retry backoff with jitter (retries
      previously fired instantly — this doc's companion
      `AI_ANALYTICS.md` wrongly claimed otherwise), honoring Groq's
      suggested wait but capped at 8s so a request never hangs on a
      daily-quota 429; answer caching by (dataset_id, normalized
      question); per-request token/latency/cost logging via a
      provider wrapper; config-driven cost (no hardcoded price — Groq's
      pricing wasn't fetchable to verify); per-user daily token quotas in
      Postgres (migration 0009, `ai_usage_log`, approved first) with a
      clear 429 and UI message; a per-user Usage page; a fallback-
      provider mechanism (built and tested, not wired — no second real
      provider exists). **Not done:** model tiering (no evidence it would
      cut tokens here), token counting for `/ask`/`/ask-sql` (they
      bypass the provider abstraction; they're still quota-blocked), an
      all-users admin view (no admin role exists), and a real 51-question
      before/after token measurement (blocked on Groq's daily cap —
      `AI_ANALYTICS.md` records the n=3 spot measurements that do exist,
      labeled as such). 42 new backend tests (292 total), 7 new frontend
      tests (19 total).
- [x] **Step 5 — Observability and reliability.** Request IDs now thread
      frontend → backend → tools → LLM: the frontend sends a fresh
      `X-Request-ID` on every call and shows it as a quotable "Reference"
      on errors; the backend honors it (validated — a malformed or
      log-injection-shaped id is replaced, never trusted), and every log
      line for that request — each tool call, each LLM call — carries it.
      Three real gaps found live and fixed along the way: an inbound id was
      ignored; an unhandled 500 carried no request id (BUG-018); and
      thread-pool work (`ThreadPoolExecutor.submit`) dropped the request's
      contextvars, which would have orphaned any log line or span inside
      it (`app/core/concurrency.py`). Optional OpenTelemetry tracing
      (vendor-neutral OTLP, chosen over LangSmith) via
      `OTEL_EXPORTER_OTLP_ENDPOINT` — off by default. Verified live
      against a real local OTLP receiver decoding the actual protobuf
      export: one request, one trace, HTTP → analyze → LLM/tool spans,
      same trace id as the logs. **That live check found BUG-017**:
      `/analyze` returned a misleading 400 when Groq failed on the first
      (tool-loop) call — fixed, and re-verified live as a degraded 200.
      Tests for the four named cases: max tool-loop iterations (rewritten
      — the old test would have passed with no cap at all), provider
      fallback, quota exceeded, cache hit. 17 new backend tests (309
      total), 5 new frontend tests (24 total).
- [~] **Step 6 — Ship it** *(built and verified locally; production deploy pending the
      V2 pull request — see docs/DEPLOYMENT.md "V2 release")*. Original scope: Switch storage to Cloudflare R2 via the
      existing `StorageProvider` (per `docs/STORAGE.md`); GitHub Actions CI
      running lint/typecheck/tests plus a fast eval subset on every PR;
      deploy backend + frontend (Render or similar) with Neon Postgres,
      every step documented in `docs/DEPLOYMENT.md` marked verified vs.
      not; a demo account + sample dataset so a recruiter can try it in
      under a minute.
- [ ] **Step 7 — Portfolio packaging.** Rewrite `README.md` — one-line
      pitch, live demo link, short GIF, Mermaid architecture diagram, eval
      results table, "key engineering decisions" (deterministic tools +
      validator over free-form answers, how NL-to-SQL stays safe, how rate
      limits are handled). New `docs/RESUME.md` — 3-4 bullets for a 1-2 YOE
      SWE (action verb first, no personal pronouns, acronyms spelled out on
      first use, only real measured numbers, ~25 words max each), one-line
      project description, a 30-second interview pitch.
- [ ] **Optional, ask first:** migrating the tool-calling loop to LangGraph
      for checkpointing/human-in-the-loop — only propose if it clearly
      improves reliability or features, with the trade-off explained before
      touching working code.

**Exit criteria:** `/analyze` is the only AI Analysis path a user reaches
in the UI (or `/ask` is explicitly, deliberately kept behind a flag), the
NL-to-SQL safety model is verified and documented, an eval harness with
recorded results exists, cost/rate-limit handling is in place and measured,
the app is deployed somewhere a recruiter can reach in under a minute, and
the README/resume materials are backed entirely by real, measured numbers.

---

## Notes

- Phase boundaries above match the `phase N+` comments already left in the
  code (`requirements.txt`, `config.py`, `router.py`) — those comments are
  the seams to build along, not just documentation.
- Storage, analytics, and AI each already have an empty package
  (`app/storage`, `app/analytics`, `app/ai`) reserved for their phase.
