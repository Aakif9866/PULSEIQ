# PulseIQ V2 — Database Plan

**Planning only — no migration is created by this document.** Everything
below is designed against the actual V1 schema (`backend/app/models/`,
`backend/alembic/versions/`), not an idealized rewrite of it. Every existing
table keeps its current shape; V2 is additive.

## Current V1 schema (for reference)

```
User
 |-- Dataset (1-N)
 |     |-- Insight (1-N, references a Dataset)
 |     +-- DashboardChart (1-N, references a Dataset)
 |-- Insight (1-N, owned directly by User)
 +-- Dashboard (1-N)
       +-- DashboardChart (1-N)
```

`User`, `Dataset`, `Insight`, `Dashboard`, `DashboardChart` — five tables,
five Alembic migrations, all cascade-deleting on their parent. This is the
foundation every V2 entity below builds on; none of it changes shape.

## Proposed V2 entities

Not all of these are required for every V2 phase — each is scoped to the
roadmap section it supports, and none should be built before the feature
that needs it (see `docs/V2_IMPLEMENTATION_PLAN.md` for sequencing).

### DatasetVersion *(supports: Dataset Management V2 — Nice to Have)*

**Purpose**: lets a re-upload be understood as a new version of an existing
logical dataset, instead of an unrelated new one.

**Important fields**: `id`, `dataset_id` (FK -> the logical `Dataset` this
version belongs to), `version_number`, `storage_key`, `size_bytes`,
`row_count`, `column_count`, `columns_profile` (JSONB) — essentially, the
version-specific fields `Dataset` already carries today, moved one level
down.

**Relationships**: `Dataset` gains a one-to-many to `DatasetVersion`; the
"current" version is either a `current_version_id` pointer on `Dataset` or
simply "the highest `version_number`" — the former is more explicit and
avoids an ambiguous query, at the cost of one extra column to keep in sync.

**Note**: this is the single most invasive V2 entity — it changes what
`Dataset` *means* (a logical dataset, not a single file) rather than purely
adding new information. It should be the last thing built, not the first,
and only once the rest of V2 has proven the simpler model is actually
limiting.

### AnalysisSession / QueryHistory *(supports: Query and Insight History)*

Two ways to model the same need — pick one, don't build both:

**Option A — `AnalysisSession`** treats "a user asking one question" (via AI
Query or the SQL Editor) as the core unit.

- **Purpose**: a record of one executed analysis, whether it came from a
  natural-language question or direct SQL.
- **Important fields**: `id`, `owner_id` (FK), `dataset_id` (FK), `question`
  (nullable — null when it came from the SQL Editor, not AI Query),
  `generated_sql` (nullable — null for a pure structured-query request, same
  as V1's `Insight.query_request` today), `query_request` (JSONB, nullable —
  populated when it's a structured query rather than raw SQL), `result_meta`
  (JSONB: row_count, columns, truncated — not the full result set),
  `chart_type` (nullable), `is_favorite` (boolean), `created_at`.
- **Relationships**: `User` 1-N, `Dataset` 1-N. This effectively generalizes
  V1's `Insight` (an `Insight` becomes "an `AnalysisSession` with an AI
  `answer` and `is_favorite=true`, surfaced under a friendlier name").

**Option B — `QueryHistory`** as a narrower, append-only log, with
`SavedQuery` and `Insight` (unchanged) as separate, deliberate "promotions"
of a history entry.

- **Purpose**: purely a log of what ran, when — no favorite flag, no
  editing.
- **Important fields**: `id`, `owner_id`, `dataset_id`, `question`
  (nullable), `sql_or_query` (JSONB or text), `result_meta` (JSONB),
  `created_at`.
- **Relationships**: `User` 1-N, `Dataset` 1-N; conceptually upstream of both
  `Insight` and `SavedQuery` (either can be "created from" a history entry,
  but neither is stored inside it).

**Recommendation**: Option B (`QueryHistory` as a plain, append-only log) is
the better fit for V1's existing style — V1's own `Insight` model is already
a deliberate, explicit "save," not an automatically-flagged one
(`docs/DATABASE.md`-equivalent reasoning: `Insight.answer` is required,
non-nullable, because it's *only* created when a save actually happens).
Keeping history separate from saving preserves that same explicit-save
philosophy instead of blurring "logged" and "saved" into one flag on one
table.

### SavedQuery *(supports: SQL Explorer)*

**Purpose**: an explicitly named, reusable SQL query — distinct from
history (automatic) and distinct from `Insight` (which pairs a query with an
AI-written answer, not just the query itself).

**Important fields**: `id`, `owner_id` (FK), `dataset_id` (FK), `name`,
`sql_text`, `created_at`, `updated_at`.

**Relationships**: `User` 1-N, `Dataset` 1-N. Deliberately has no
`generated_sql` vs `query_request` split like `QueryHistory` above — a
`SavedQuery` is always raw SQL, because it only makes sense once the SQL
Explorer exists; saving a structured (non-SQL) query is already served by
V1's existing `Insight`/`DashboardChart.query_request` pattern.

### Dashboard *(extended, not replaced)*

V1's `Dashboard` (`id`, `owner_id`, `name`) stays exactly as-is. V2 adds:

- **`layout`** (JSONB, nullable) — per-chart position/size overrides once
  resize/reorder exist (Section "Advanced Interactive Dashboard" in
  `docs/V2_ROADMAP.md`), keyed by `DashboardChart.id` so it doesn't require
  touching the chart rows themselves.
- **`filters`** (JSONB, nullable) — dashboard-level filter state (e.g. an
  active date range) applied on top of each chart's own stored
  `query_request` at render time.

**Relationships**: unchanged — still 1-N from `User`, still 1-N to
`DashboardChart`.

### DashboardChart *(extended, not replaced)*

V1's `DashboardChart` already carries `chart_type` as a plain string
(`"bar" | "line"`) — V2 only needs to widen the *values* that column accepts
(`"area"`, `"pie"`, `"scatter"`, `"kpi"`, `"table"`), not its shape. No
schema change is strictly required here beyond removing an application-level
validation constraint; this is called out specifically so it isn't
mistaken for a bigger change than it is.

---

## Simplified ER-style diagram (V2, additive)

```
User
 |-- Dataset (1-N)
 |     |-- DatasetVersion (1-N)                [Nice to Have, built last]
 |     |-- Insight (1-N)                       [unchanged from V1]
 |     |-- QueryHistory (1-N)                  [new]
 |     |-- SavedQuery (1-N)                    [new]
 |     +-- DashboardChart (1-N)                [unchanged shape, wider chart_type values]
 |-- Insight (1-N)                             [unchanged from V1]
 |-- QueryHistory (1-N)                        [new]
 |-- SavedQuery (1-N)                          [new]
 +-- Dashboard (1-N)                           [+layout, +filters JSONB]
       +-- DashboardChart (1-N)
```

## Design principles carried over from V1

- Every new entity is owner-scoped (`owner_id`) exactly like every existing
  one — no new entity should be reachable without an ownership check, ever.
- Every new entity's foreign keys use `ondelete="CASCADE"`, matching V1's
  existing convention (delete a dataset, its history/saved queries/insights/
  chart references go with it).
- JSONB is used the same way V1 already uses it — for genuinely flexible,
  schema-varying data (a query shape, a result-metadata summary) — not as a
  substitute for real columns where the shape is actually fixed and known.
- No entity here requires a new database engine, a new ORM, or a change to
  how migrations are run (Alembic, one migration per logical change,
  reviewed and run in CI against a real Postgres container) — V2's database
  work is more tables of the same kind, not a different kind of database
  work.
