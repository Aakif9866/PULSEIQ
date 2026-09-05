# PulseIQ V2 — Implementation Plan

**Planning only — no code in this branch.** Phases are ordered by
dependency (what needs what) and by how directly each extends V1's existing
strengths. No time estimates are given, per instruction — "complexity" below
is relative (Low / Medium / High), not a duration.

Each phase is designed to be shippable and independently valuable — a
developer could stop after any phase and V1 plus that phase would be a
coherent, working application, not a half-finished feature.

---

## Phase 1 — Natural Language to SQL

**Goal**: let an AI-answered question be backed by a real, validated SQL
query instead of only the closed structured-query schema, finally giving the
already-declared DuckDB dependency a real job.

**Features**: schema-context generation (extending V1's existing column
profile with distinct-value sampling for low-cardinality columns), a new
SQL-generation prompt/call, the SQL Validation Layer (parse, allow-list,
bound), DuckDB execution against the in-memory dataset, and returning the
generated SQL alongside the AI's answer.

**Files likely affected**:
- New: `app/ai/sql_generator.py` (or similar) — the SQL-generation prompt/call
- New: `app/analytics/sql_validator.py` — parsing + allow-listing
- New: `app/analytics/sql_engine.py` — DuckDB execution against a registered Polars view
- Extended: `app/services/analyst_service.py` — a new path alongside the existing structured-query one
- Extended: `app/schemas/ai.py` — `AskResponse` gains an optional `generated_sql` field
- Extended: `app/core/config.py` — a SQL-specific timeout/row-limit setting, following V1's existing `QUERY_TIMEOUT_SECONDS`/`QUERY_ROW_LIMIT` naming
- Frontend: `ai-analyst-page.tsx` — display the generated SQL alongside the answer

**New database requirements**: none for this phase alone — SQL generation
and execution don't require persisting anything new.

**Technical risks**:
- **The single biggest risk in the entire V2 roadmap**: an AI-generated SQL
  statement reaching a real execution engine. Mitigated by the layered
  validation described in `docs/V2_ROADMAP.md` (parse via a real SQL parser,
  statement-type allow-list, table/column allow-list, resource bounds,
  disposable connection) — not optional, not a "phase 2 hardening" item.
  This phase should not be considered complete until that validation exists
  and has its own dedicated tests (see Testing below).
- Plain-text SQL generation (no JSON-mode equivalent for raw SQL) means
  malformed output is more likely than V1's JSON-mode structured queries —
  the validator must reject cleanly, not attempt to "fix" ambiguous SQL.

**Testing requirements**: unit tests for the validator specifically
targeting rejection — multi-statement injection, DDL/DML statements,
references to nonexistent tables/columns, and known DuckDB-specific risks
(`ATTACH`, `COPY`, `read_csv` of an arbitrary path) — mirroring V1's existing
`test_dataset_query.py`'s "unknown column rejected" pattern, extended to a
SQL-shaped input instead of a structured one. Integration tests exercising
the full question → SQL → execution → answer path, reusing V1's existing
`test_ai_analyst.py` fixtures/style.

**Estimated complexity**: High (the validation layer, done properly, is
real, careful work — this is the phase where cutting corners would matter
most).

---

## Phase 2 — SQL Explorer and Query History

**Goal**: give users a direct SQL editor (not just AI-generated SQL), and
start persisting what's actually been asked/run.

**Features**: the SQL Editor tab (frontend), the `QueryHistory` entity and a
history list, saved queries, schema-derived suggested queries (no AI call
needed for these).

**Files likely affected**:
- New: `backend/alembic/versions/000X_create_query_history.py`,
  `..._create_saved_queries.py`
- New: `app/models/query_history.py`, `app/models/saved_query.py`
- New: `app/repositories/query_history_repository.py`,
  `saved_query_repository.py`
- New: `app/services/history_service.py`
- New: `app/api/v1/history.py`, extended `app/api/v1/analysis.py` (a
  direct-SQL endpoint, reusing Phase 1's validator)
- Frontend: new `dataset-sql-explorer` view/tab, `features/history/api.ts`

**New database requirements**: `QueryHistory` and `SavedQuery` tables (see
`docs/V2_DATABASE_PLAN.md`) — both owner-and-dataset-scoped, both
cascade-deleting, following V1's existing migration style exactly.

**Technical risks**: mostly low — this phase is largely "more of the same
kind of thing V1 already does" (another owned entity, another repository,
another router) layered on top of Phase 1's validator rather than
introducing new execution risk. The one real risk: deciding what
"history" actually stores (see the Option A/B discussion in
`docs/V2_DATABASE_PLAN.md`) — getting this entity's shape wrong early would
be more annoying to fix later than most of V2's other tables, since history
is expected to accumulate quickly.

**Testing requirements**: repository/service tests for ownership isolation
(reusing V1's existing "cannot access another user's X" test pattern, now
for history/saved queries); a test confirming the SQL Editor's direct-run
path goes through the exact same validator Phase 1 built, not a second,
divergent one.

**Estimated complexity**: Medium.

---

## Phase 3 — Advanced Interactive Dashboard (part 1: chart types, reorder, multiple dashboards)

**Goal**: the lower-risk half of the dashboard roadmap — more chart types,
basic reordering, and multiple named dashboards per user (already close to
free given V1's existing `Dashboard` model).

**Features**: area/pie/scatter/KPI-card/table chart types, drag-reorder
(`position`), multiple dashboards surfaced clearly in the UI.

**Files likely affected**:
- Extended: `lib/chart-options.ts` (new chart-type branches), new
  `kpi-card.tsx` / `result-table.tsx` components
- Extended: `components/dashboards/chart-card.tsx` — render the right
  component per `chart_type`
- Extended: `dashboards-page.tsx`, `dashboard-detail-page.tsx`
- Backend: widen the accepted `chart_type` values in
  `app/schemas/dashboard.py` — likely no other backend change

**New database requirements**: none — `position` already exists;
`chart_type` is already a plain string column, just validated more widely.

**Technical risks**: low. The main risk is scope creep — resist pulling in
resize/filters/cross-filtering here (they're Phase 4 and future work
respectively) just because "dashboards" is one word in the roadmap.

**Testing requirements**: frontend component tests for the new chart types
(if a frontend testing setup exists by this point — see the note in
`docs/PULSEIQ_SKILLS.md`'s skill-gap section that no frontend tests exist
today; this phase is a reasonable place to introduce the first ones, but
that's a prerequisite worth naming, not an assumption).

**Estimated complexity**: Low–Medium.

---

## Phase 4 — Advanced Interactive Dashboard (part 2: resize, filters, saved layout)

**Goal**: the higher-effort half of the dashboard roadmap, deliberately
sequenced after Phase 3 proves the simpler pieces out.

**Features**: resizable widgets, dashboard-level filters (category, date
range) applied on top of each chart's stored query, persisted layout state.

**Files likely affected**:
- New frontend dependency: a grid/resize library (the only phase in this
  entire plan that requires adding a new frontend dependency)
- Extended: `app/models/dashboard.py` (`layout`, `filters` JSONB columns),
  a new Alembic migration
- Extended: `app/services/dashboard_service.py` — apply dashboard-level
  filters on top of each chart's query at render time

**New database requirements**: `layout` and `filters` JSONB columns on
`Dashboard` (additive, nullable — see `docs/V2_DATABASE_PLAN.md`).

**Technical risks**: applying a dashboard-level filter on top of an
already-stored `query_request` needs a clear, tested merge rule (does a
dashboard filter override a chart's own filter on the same column, or
combine with it?) — an ambiguity worth resolving on paper before writing
the merge code, not discovering it mid-implementation.

**Testing requirements**: tests specifically for the filter-merge rule
(same category as `test_dataset_query.py`'s filter tests, extended to two
filter sources instead of one).

**Estimated complexity**: Medium–High.

---

## Phase 5 — AI Chart Intelligence

**Goal**: suggest (never silently apply) a chart configuration for a query
result, using the deterministic rules-table approach from
`docs/V2_ROADMAP.md` — not a new AI call for the common case.

**Features**: the chart-shape rules table, a fixed-enum fallback AI call for
ambiguous cases only, a "suggested — change it" UI affordance.

**Files likely affected**:
- New: `app/analytics/chart_suggestion.py` (the rules table)
- Extended: `app/services/analyst_service.py` — attach a suggestion to
  `AskResponse`
- Frontend: `ai-analyst-page.tsx` — show the suggested chart type as a
  pre-selected, changeable option

**New database requirements**: none.

**Technical risks**: the temptation to make this a third free-form AI call
instead of a rules table — worth resisting explicitly, since a
non-deterministic chart-type choice is much harder to test and to explain in
an interview than a deterministic one with a narrow, bounded AI fallback.

**Testing requirements**: unit tests for the rules table directly (given a
query shape, assert the expected chart type) — these should be simple,
numerous, and fast, since the whole point of the rules-table design is that
it's testable in a way an AI call isn't.

**Estimated complexity**: Low–Medium (specifically because the design in
`docs/V2_ROADMAP.md` deliberately avoids the harder, AI-first version of
this feature).

---

## Phase 6 — Data Quality and Profiling

**Goal**: extend `profile_dataframe()` with the richer statistics described
in `docs/V2_ROADMAP.md` — missing %, duplicates, outliers, distributions,
correlation, a transparent quality score, and an optional AI-generated
summary.

**Files likely affected**:
- Extended: `app/analytics/profiling.py`
- Extended: `app/models/dataset.py` — either widen `columns_profile`'s JSONB
  shape (no migration needed, it's already schema-less JSONB) or add a
  handful of new top-level columns (`duplicate_row_count`,
  `data_quality_score`) if those should be queryable/sortable rather than
  buried in JSONB
- Frontend: a new "Data Quality" tab/section on the dataset explorer page

**New database requirements**: none to a couple of new columns on `Dataset`
depending on the JSONB-vs-column decision above.

**Technical risks**: low computationally (Polars already provides most of
what's needed); the real risk is scope — a "data quality score" can expand
indefinitely in sophistication. This phase should ship a simple, explainable
version first (explicitly not a black-box ML model, per
`docs/V2_ROADMAP.md`) rather than block on a more elaborate one.

**Testing requirements**: unit tests per new statistic (duplicate count,
missing %, outlier flag) against small, hand-constructed DataFrames with
known expected output — the same style V1's existing profiling/query tests
already use.

**Estimated complexity**: Low–Medium.

---

## Phase 7 — Persistent Object Storage

**Goal**: actually run `R2StorageProvider` against real Cloudflare
credentials in production — closing the single biggest gap between
"deployed" and "production-ready" that exists in V1 today.

**Features**: switching `STORAGE_PROVIDER=r2` on the deployed Railway
backend with real credentials; verifying uploads survive a redeploy; wiring
up the already-reserved `ENABLE_STORAGE_CLEANUP`/`DATASET_RETENTION_DAYS`
settings to an actual cleanup path.

**Files likely affected**: potentially none — `R2StorageProvider` already
exists and is unit-tested (`app/storage/r2.py`, `tests/test_storage.py`
equivalents). This phase may be **configuration and verification work
only**, which is worth stating plainly rather than implying new code is
needed where it might not be.

**New database requirements**: none.

**Technical risks**: the main risk is discovering the existing
`R2StorageProvider` implementation has a gap that only real credentials
would expose (untested against a real Cloudflare account today) — this
phase should start with a real-credentials verification pass before assuming
no code changes are needed.

**Testing requirements**: the same real-platform verification discipline
already used for the Railway deployment itself — a real upload, a real
redeploy, a real confirmation the file is still retrievable afterward, not
just unit tests passing against a mock.

**Estimated complexity**: Low (if the existing implementation holds up) to
Medium (if real-credential testing surfaces a gap).

---

## Sequencing summary

```
Phase 1 (SQL generation + validation)
        |
        v
Phase 2 (SQL Explorer + History)  -- depends on Phase 1's validator
        |
        v
Phase 3 (Dashboard: chart types, reorder, multi-dashboard) -- independent, could run parallel to 1/2
        |
        v
Phase 4 (Dashboard: resize, filters) -- depends on Phase 3
        |
        v
Phase 5 (AI Chart Intelligence) -- benefits from Phase 3's chart types existing first
        |
        v
Phase 6 (Data Quality) -- independent, could run any time after V1
        |
        v
Phase 7 (Persistent Storage) -- independent, could run any time, arguably first if storage risk is the top priority
```

Phases 3 and 6 have no hard dependency on Phases 1/2 and could be reordered
earlier if the SQL work proves harder than expected — see
`docs/V2_FEATURES.md` for the recommended priority order and the reasoning
behind it.
