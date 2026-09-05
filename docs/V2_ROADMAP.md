# PulseIQ V2 Vision

**Status of this document: planning only. Nothing described here is
implemented. V1 remains the deployed, working application.**

## Where PulseIQ is today

> "An application where users upload data and ask AI for analysis."

A user uploads a CSV/XLSX file, the backend profiles it with Polars, and the
user can either build a structured query visually (group by / aggregate /
filter / sort) or ask a plain-English question that an AI (Groq) answers —
grounded in a result the backend actually computed, never a guessed number.
Results become a bar/line chart, can be pinned to a dashboard, or saved as a
named insight. That's genuinely useful, and it's genuinely deployed.

## Where V2 should move it toward

> "An AI-powered self-service analytics platform where users can explore,
> query, visualize, and understand their data interactively."

The gap between those two sentences is really four things, in priority
order:

1. **More expressive analysis** — today's structured query schema (Section 4
   of `docs/AI_ANALYTICS.md`) can't express joins, window functions, or
   anything beyond one flat table. A real SQL layer (finally using the
   already-declared DuckDB dependency) closes this.
2. **More expressive visualization** — today there are exactly two chart
   types (bar, line), chosen manually by the user. A real dashboard needs
   more chart types and some AI help choosing between them.
3. **Memory** — today nothing is remembered except an explicitly-saved
   Insight. There's no query history, no "run that again," no favorites.
4. **Trustworthy data at scale** — today storage is local disk (ephemeral on
   Railway) and profiling is a handful of stats. Real self-service analytics
   needs data quality visibility and storage that survives a redeploy.

This roadmap is scoped for **one developer, working gradually, on a
portfolio project** — not a team, not an enterprise system. Every phase in
`docs/V2_IMPLEMENTATION_PLAN.md` is sized to be buildable and shippable on
its own, in isolation, without the others.

---

## Master Roadmap (executive summary)

### 1. What is PulseIQ V1?

A full-stack analytics app: React/TypeScript frontend, FastAPI/Python
backend, PostgreSQL (Neon) for application data, Polars for all dataset
computation, Groq for AI-assisted question answering. Deployed as two
Docker-based Railway services with a GitHub Actions CI pipeline. Full detail
in `docs/ARCHITECTURE.md` and `docs/AI_ANALYTICS.md`; every known bug and its
fix is in `docs/BUGS.md`.

### 2. What are its current strengths?

A real, working end-to-end flow (upload → profile → query/ask → visualize →
save); a safe-by-construction query layer (a closed schema, not generated
SQL, so there's no injection surface today); an AI design that structurally
can't state a number it didn't compute; a genuinely deployed, CI-tested
codebase, not just a local prototype.

### 3. What are its current limitations?

See "Current V1 Limitations" below — the short version: no SQL/joins, only
two chart types chosen manually, no history/memory beyond explicit saves,
local disk storage that doesn't survive a Railway redeploy, and a DuckDB
dependency that's declared but never used.

### 4. What should V2 become?

The four pillars above: a real (but safely sandboxed) SQL layer, richer
dashboards with AI-assisted chart selection, persistent analytics history,
and durable object storage with real data-quality visibility.

### 5. Which features should be implemented first?

Natural Language to SQL (Phase 1) and SQL Explorer (Phase 2) — see
"Recommended implementation order" reasoning in `docs/V2_FEATURES.md`. They
directly extend the project's existing, best-understood strength (the query
layer) and finally give the already-declared DuckDB dependency a real job.

### 6. Which features should wait?

Persistent object storage and full data-quality profiling are valuable but
lower-urgency — the app works today with their current limitations openly
documented rather than hidden. Full detail and reasoning in
`docs/V2_FEATURES.md`.

### 7. What architecture changes will eventually be required?

A new SQL validation layer between the AI and DuckDB; DuckDB introduced as a
real, in-process execution engine (not just a dependency); dashboard state
becoming richer (widget layout, filters) instead of a flat list of charts.
No new services, no new deployment targets — everything fits inside the
existing FastAPI monolith. Full diagrams in `docs/V2_ARCHITECTURE.md`.

### 8. What database changes may be required?

New tables for query/analysis history and saved SQL queries; dashboards
gaining layout/filter state; datasets optionally gaining a lightweight
versioning concept. No existing table needs to be dropped or fundamentally
reshaped. Full entity plan in `docs/V2_DATABASE_PLAN.md`.

### 9. What are the major technical risks?

Safely validating and sandboxing AI-generated SQL is the single biggest risk
in this whole roadmap — it's the one place a mistake has real consequences
(unlike the current structured-query schema, which has no attack surface by
construction). Chart-type "intelligence" risks being unreliable in a way
that's hard to test. Both are called out explicitly, with mitigations, in
`docs/V2_IMPLEMENTATION_PLAN.md`.

### 10. What would make PulseIQ a genuinely advanced portfolio project?

Shipping the SQL layer safely — with a real validation/sandboxing story a
reviewer can be walked through in an interview — would do more for PulseIQ's
portfolio value than any other single feature here. A closed, structured
query schema is a good junior-to-mid-level story; a validated, sandboxed
natural-language-to-SQL pipeline is a noticeably stronger one, precisely
because it requires taking the current design's safety guarantee (no
generated SQL exists) and rebuilding an equivalent guarantee on top of a much
riskier primitive.

---

## Current V1 Features

Verified against the actual codebase, not assumed:

- **Auth**: signup/login, JWT access (24h) + refresh (14d) tokens, bcrypt
  password hashing.
- **Dataset upload**: `.csv`, `.xlsx`, `.xls` accepted (only `.csv`/`.xlsx`
  actually parse — see limitations); size-limited via `MAX_UPLOAD_SIZE_MB`.
- **Storage**: a `StorageProvider` abstraction with a working local-disk
  implementation (deployed) and a written, unit-tested R2 (S3-compatible)
  implementation (not yet run against real credentials).
- **Dataset processing**: synchronous profiling on upload via Polars — row
  count, column count, per-column dtype, per-column null count. A real fix
  exists for CSV columns with leading zeros (e.g. zip codes).
- **Query engine**: a closed, structured schema (`group_by` / `aggregations`
  / `filters` / `sort_by` / `limit`), executed entirely in-memory by Polars.
  No SQL text exists anywhere in this path.
- **DuckDB**: declared in `requirements.txt`, **not imported or called
  anywhere in `app/`**. This is the single most important fact this roadmap
  is built around — V2's Natural Language to SQL feature is what finally
  gives this dependency a job.
- **AI analysis**: a two-call Groq pipeline — question + column profile →
  structured query (JSON mode, validated by Pydantic against the same schema
  the manual query builder uses) → the backend actually runs it → question +
  real result → plain-language answer.
- **Charts**: bar and line only, manually selected by the user, rendered
  with ECharts from a query result.
- **Dashboards**: a named collection of pinned charts; each chart re-runs its
  stored query on every dashboard load (always current, never stale data).
- **Saved insights**: a question + AI answer + the underlying query, kept
  together so a saved insight stays reproducible.
- **CI/CD**: GitHub Actions — backend (ruff, mypy, real Postgres migrations,
  pytest) and frontend (oxlint, tsc, production build) — on every push/PR.
- **Deployment**: Railway, two Docker-built services (backend + frontend) in
  one project; Neon Postgres unchanged across every environment.

## Current V1 Limitations

Stated plainly, matching `docs/BUGS.md` / `docs/STORAGE.md` /
`docs/SECURITY.md` — these are what V2 exists to address, not oversights:

- **No SQL, no joins, no window functions** — the structured query schema
  can only express one flat table's group/aggregate/filter/sort. Anything
  needing more than that (comparisons across two derived aggregates, ranking,
  running totals) can't be expressed today.
- **Only two chart types**, chosen manually — no pie/donut, scatter, heatmap,
  area, or KPI cards, and no AI assistance in choosing between them.
- **No history or memory** beyond an explicit "save as insight" — a question
  asked and not saved is gone; there's no query history, no favorites, no
  "run this again."
- **Local disk storage is ephemeral on Railway** without an attached volume —
  uploaded files may not survive a redeploy even though their database
  metadata does.
- **Profiling is shallow** — row/column counts and per-column dtype/null
  count only; no outlier detection, no distributions, no duplicate-row
  detection, no correlation analysis, no data-quality score.
- **No dataset versioning** — re-uploading replaces nothing and creates a new
  independent dataset; there's no concept of "a new version of the same
  dataset."
- **DuckDB is inert** — a real, if narrow, gap between what the dependency
  list implies and what the app does.

---

## Natural Language to SQL

The centerpiece of V2. This is the feature that finally uses DuckDB for
something real, and the one place this roadmap asks for real caution.

### Flow

```
User Question
        |
        v
Dataset Schema Context  (column names, types, a small sample of distinct
                          values for low-cardinality columns — generated
                          the same way today's column profile already is)
        |
        v
AI Model (Groq, JSON mode)  -->  generates a SQL SELECT statement, not
                                  natural-language JSON this time
        |
        v
SQL Safety Validation  (a dedicated layer — see below — before anything runs)
        |
        v
DuckDB Execution  (against the same in-memory Polars DataFrame, registered
                   as a DuckDB view — no separate data copy or ingestion step)
        |
        v
Results  (columns + rows, same shape contract as today's DatasetQueryResult)
        |
        v
AI Explanation  (a second Groq call, same "summarize the real result"
                 pattern V1 already uses — reused, not reinvented)
        |
        v
Visualization Suggestion  (see "AI Visualization Intelligence" below)
```

### How schema context should be generated

Reuse exactly what V1 already computes and stores as `columns_profile`
(name + dtype + null_count) — no new profiling work needed for this part.
The one addition worth considering: for low-cardinality string columns
(e.g. under ~20 distinct values — a "category" or "region" column), include
the actual distinct values in the prompt. This is what makes a question like
"compare profit margins across categories" answerable — the model needs to
know what a "category" actually contains, not just that the column exists.

### How SQL should be generated

A dedicated system prompt (separate from V1's `_QUERY_SYSTEM_PROMPT`)
instructing the model: generate exactly one `SELECT` statement, against a
single table named consistently (e.g. `dataset`), using only the columns
listed in the schema context, with no DDL/DML keywords anywhere. JSON mode
is not usable for raw SQL text the way it is for V1's structured query (JSON
mode forces valid JSON, not valid SQL) — so this call is plain-text
completion, which means the validation layer below carries more weight than
V1's Pydantic-schema validation does.

### How SQL should be validated

This is the one place this roadmap asks for defense in depth, not a single
check:

1. **Parse, don't regex.** Use a real SQL parser (e.g. `sqlglot`, which can
   parse without executing) to get a structured AST — regex-based
   "does it contain DROP" checks are exactly the kind of unsafe shortcut this
   roadmap explicitly wants to avoid.
2. **Statement-type allow-list.** The parsed statement must be a single
   `SELECT`. Anything else (`INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`,
   `CREATE`, `ATTACH`, `COPY`, `PRAGMA`, multiple statements separated by
   `;`) is rejected before DuckDB ever sees it.
3. **Table/column allow-list.** Every table reference must be the single
   registered dataset view; every column reference must exist in that
   dataset's real schema. This reuses the same `_require_columns`-style
   validation V1's query engine already does, just walking a SQL AST instead
   of a Pydantic model.
4. **Resource bounds.** A hard `LIMIT` injected server-side if the model
   didn't include one (reusing V1's existing `QUERY_ROW_LIMIT` idea), and the
   same `QUERY_TIMEOUT_SECONDS`-bounded execution pattern V1 already uses for
   Polars queries, applied to the DuckDB call instead.
5. **A fresh, disposable DuckDB connection per query**, with the dataset
   registered as the only table — never a shared, persistent DuckDB database
   file, and never file-system or network access enabled for that
   connection.

### How destructive or unsafe queries should be blocked

By construction, not by trying to enumerate every bad case: since only a
single `SELECT` statement referencing an allow-listed table/columns is ever
allowed to reach DuckDB, `DROP TABLE`, `DELETE`, multi-statement injection,
and file/network access (`ATTACH`, `COPY TO`, `read_csv('/etc/passwd')`, etc.)
are all rejected at the parse/allow-list stage before execution, not caught
after the fact.

### How execution errors should be handled

The same pattern V1 already uses for `InvalidQueryError`/`ColumnNotFoundError`
— a domain-specific exception, mapped to a clean 4xx, never a raw DuckDB
error string (which could leak the query itself or internal detail) shown
directly to the user. The generated SQL itself, though, **should** be shown
to the user (see below) — the distinction is "don't leak an internal error
message," not "hide the query."

### How generated SQL can be shown to the user

Every AI-answered question should return the exact SQL that was run
alongside the answer — mirroring how V1's `AskResponse` already returns the
structured `query` alongside the `answer` today. This is both a trust signal
(the user can see what actually ran) and the natural bridge into the SQL
Explorer below (a "generated this — open in SQL Explorer" action).

### How users can copy or reuse SQL

A copy-to-clipboard action next to the displayed SQL, and a "save as query"
action that persists it (see `docs/V2_DATABASE_PLAN.md`'s `SavedQuery`
entity) for later reuse from the SQL Explorer without re-asking the AI.

---

## SQL Explorer

A second, complementary way to reach the same DuckDB execution path — for
users who'd rather write SQL directly than ask in English.

**Proposed interface**: a two-tab view on the dataset explorer page —
`AI Query` (today's ask-a-question flow, extended with the SQL step above)
and `SQL Editor` (a direct text editor).

| Feature | Purpose |
|---|---|
| SQL editor | Free-text SQL input, syntax highlighting (a lightweight client-side library, not a new backend dependency) |
| Run query | Submits to the exact same validation + DuckDB execution path Natural Language to SQL uses — one execution engine, two entry points |
| Query history | A running list of every query executed this session/persistently (see `docs/V2_DATABASE_PLAN.md`) |
| Generated SQL | When arriving from the AI Query tab, pre-fills the editor with the AI's generated SQL, editable before re-running |
| Copy SQL | Copies the current editor content |
| Saved queries | Explicit, named saves (distinct from automatic history) |
| Query result table | Same result-table component the manual query builder already renders results in — reused, not rebuilt |
| Query execution errors | Same safe, non-leaking error handling as above, shown inline near the editor |
| Suggested queries | A small set of template queries generated from the dataset's schema (e.g. "SELECT * FROM dataset LIMIT 100", one groupby-count per low-cardinality column) — not AI-generated, just schema-derived, so this needs no model call at all |

### Integration with the existing engine

The SQL Explorer and Natural Language to SQL should share **one** validation
+ execution function — the SQL Explorer is simply a second caller of it,
skipping the "generate SQL from a question" step and going straight to
"validate and run this SQL." This mirrors how V1's AI Analyst already reuses
the exact same `run_query()` the manual query builder calls — the same
architectural pattern, one layer up.

---

## Advanced Interactive Dashboard

V1's dashboard today: a named list of charts, each a stored
`(dataset_id, query_request, chart_type, title, position)`, re-run on every
load. V2 should grow this deliberately, not all at once.

| Feature | User value | Technical approach | Difficulty | Dependencies | Phase |
|---|---|---|---|---|---|
| More chart types (area, pie/donut, scatter, KPI card, table) | Matches the actual shape of more questions (a single KPI number, a part-to-whole comparison) | Extend `buildChartOption()` and `chart_type` with new cases; KPI card and table need their own (simple) React components, not ECharts | Low–Medium | None new | V2 Phase 3 |
| Multiple dashboards per user | Separate "Sales" vs "Support" views instead of one shared list | Already almost there — `Dashboard` is already a named, owned entity; this is close to free | Low | None new | V2 Phase 3 |
| Reorder widgets | Basic usability once a dashboard has more than a few charts | `position` already exists on `DashboardChart`; needs a drag-reorder UI only | Low | A drag-and-drop library (new frontend dependency) | V2 Phase 3 |
| Resize widgets | Lets a KPI card be small and a trend chart be large | Store a width/height alongside `position`; a CSS-grid-based layout on the frontend | Medium | Same drag-and-drop library, ideally one that also handles resize | V2 Phase 3 |
| Filters (category, date range) | Lets one dashboard answer more than one question without rebuilding it | Add an optional `filters` override applied on top of each chart's stored `query_request` at render time — reuses V1's existing filter schema, doesn't invent a new one | Medium | None new | V2 Phase 4 |
| Cross-filtering (click one chart, filter the others) | The single most "wow" interactive-dashboard feature | Requires dashboard-level shared filter state and every chart re-querying on change — meaningfully more frontend state management than anything in V1 today | High | None new, but real frontend complexity | Future work (post-V2 phase list) |
| Drag-and-drop widget placement (freeform, not just reorder) | Polished, "real BI tool" feel | A grid layout library (e.g. `react-grid-layout`) storing an explicit layout blob | Medium–High | New frontend dependency | Future work |
| Save dashboard state (layout/filters) | Makes resize/reorder/filters actually persist | A `layout` JSONB column on `Dashboard` (see `docs/V2_DATABASE_PLAN.md`) | Low | None new | V2 Phase 3 (paired with reorder/resize) |

**Sequencing note**: reorder + more chart types + multiple dashboards are the
right first slice (mostly reusing what already exists); resize and filters
follow once that's solid; cross-filtering and true drag-and-drop placement
are explicitly future work — real value, but a large jump in frontend state
complexity that shouldn't block shipping the rest.

---

## AI Visualization Intelligence

V1's AI never touches visualization — the user always manually picks bar or
line. V2 proposes the AI *suggest* a chart configuration, always as a
suggestion the user can override, never an automatic, silent choice.

### Example

Question: *"Show me how sales changed across regions over time."*

Suggested configuration:

```
Chart Type: Line
X-axis:     order_date
Y-axis:     SUM(sales)
Group By:   region
```

### How this can be implemented safely and reliably

The key design decision: **this is a classification/suggestion problem, not
a new generation problem** — it should not be a third free-form AI call.
Instead:

1. The AI's existing structured-query (or, in V2, generated-SQL) output
   already implies most of this: if the query groups by a date-typed column
   and aggregates a numeric column, "line chart over time" is a deterministic
   rule, not something that needs to be asked of the model separately.
2. A small, explicit rules table maps query shape → suggested chart type
   (e.g.: one group-by column that's a date → line; one group-by column
   that's low-cardinality categorical + one aggregation → bar; no group-by,
   a single aggregation → KPI card; two numeric columns with no aggregation →
   scatter). This is ordinary code, not a model call — reliable and testable,
   which an LLM call for the same decision would not be.
3. Only when the rules table can't confidently decide (an ambiguous shape)
   should a model call be considered at all, and even then it should return
   a choice from a fixed enum of chart types (reusing the JSON-mode pattern
   V1 already uses for structured queries) — never free text.
4. The suggestion is always presented as *pre-selected but changeable* in the
   UI, never auto-applied without the option to switch it — consistent with
   this whole roadmap's principle that AI proposes, the system (or the user)
   decides.

This keeps the riskiest part of "AI visualization intelligence" — an LLM
guessing something structural — out of the design entirely for the common
case, and bounded (fixed enum, JSON mode) for the rare case.

---

## Query and Insight History

V1 remembers only what's explicitly saved as an Insight. V2 proposes a
persistent, lightweight history layer underneath that.

### Proposed features

- **Recent AI questions** — every question asked (not just saved ones),
  most-recent-first, per dataset or across all datasets.
- **Generated SQL / structured query** — stored alongside each history
  entry, exactly like V1 already stores `query_request` on a saved `Insight`.
- **Results metadata** — row count, column names, truncated flag — not the
  full result set (avoids storing potentially large/stale data; a history
  entry is re-run to get fresh results, not replayed from a stored blob).
- **Generated charts** — if a chart was rendered from a history entry, which
  chart type was used.
- **Favorite queries** — a boolean flag on a history entry, promoting it
  without needing the full "save as Insight" flow.
- **Re-run previous analysis** — one action that takes a history entry's
  stored query/SQL and re-executes it fresh against the dataset's current
  state.

### Database changes (high level only — no migration here)

A new table, tentatively `analysis_history` (see the `AnalysisSession` /
`QueryHistory` entities in `docs/V2_DATABASE_PLAN.md` for the actual shape):
owner-scoped and dataset-scoped like every other V1 entity, storing the
question (if any), the query/SQL that was run, a small results-metadata
JSONB blob, a `favorite` flag, and a timestamp. This is additive — no
existing table changes shape.

---

## Dataset Management V2

| Capability | Priority |
|---|---|
| Persistent object storage (R2 actually in use, not just written) | **Must Have** — the single biggest gap between "deployed" and "production-ready" today |
| Dataset expiration/deletion policy (the already-reserved `DATASET_RETENTION_DAYS`/`ENABLE_STORAGE_CLEANUP` settings, finally acted on) | **Must Have** — these settings already exist in `app/core/config.py`, inert; wiring them up is mostly finishing something already started |
| Row/column statistics beyond today's dtype+null-count (distributions, min/max, cardinality) | **Should Have** — direct input to both AI Visualization Intelligence's rules table and Data Quality profiling below |
| Duplicate row detection | **Should Have** — a common, expected "data quality" feature; cheap to compute in Polars (`.is_duplicated()`) |
| Missing-value analysis (beyond a raw null count — e.g. % missing per column, flagged if above a threshold) | **Should Have** |
| Column type detection improvements (e.g. detecting a string column that's actually a date, or a categorical column) | **Should Have** — improves both profiling and AI schema context quality |
| Dataset versioning (re-upload creates a new version of the same logical dataset, not an unrelated one) | **Nice to Have** — real value, but a genuinely new modeling concept (see `DatasetVersion` in `docs/V2_DATABASE_PLAN.md`) that touches more of the existing dataset code than anything else in this list |
| Dataset refresh (re-fetch/re-process without a full re-upload) | **Nice to Have** — only meaningful once there's a real external data source to refresh from; today's only ingestion path is a manual file upload, so this has no clear trigger yet |

---

## Data Profiling and Data Quality

V1's profiling today: row count, column count, per-column dtype, per-column
null count — computed once, synchronously, on upload.

| Feature | How it could work |
|---|---|
| Missing values (richer than today) | Already have `null_count` per column; add `null_percentage` and a simple threshold-based flag — pure Polars, no new dependency |
| Duplicate rows | `df.is_duplicated().sum()` in Polars — cheap, already the right tool |
| Outliers | For numeric columns, a simple IQR or z-score check in Polars — no need for DuckDB or a stats library beyond what Polars' `.quantile()` already provides |
| Column distributions | For numeric columns: min/max/mean/std (Polars' `.describe()`-style aggregations); for categorical columns: top-N value counts (`.value_counts()`) |
| Numeric statistics | As above — extends `profile_dataframe()` in `app/analytics/profiling.py`, doesn't replace it |
| Categorical statistics | Top-N value counts + distinct count per column |
| Correlation analysis | Polars supports pairwise correlation for numeric columns directly (`.corr()`); this is the one profiling feature genuinely better suited to DuckDB if the dataset is wide, since a full correlation matrix is naturally expressible as SQL over the DuckDB view already introduced for Natural Language to SQL — a good example of the two engines being complementary rather than redundant |
| Data quality score | A simple, transparent weighted score (e.g. based on missing %, duplicate %, outlier %) — deliberately not a black-box ML model; a portfolio project benefits far more from an explainable score than an opaque one |
| AI-generated dataset summary | A third, optional AI call: profile stats → one paragraph in plain English ("this dataset has 12,000 rows, 3% missing values concentrated in the `discount` column, and 40 duplicate rows") — reuses the exact "give the AI real computed numbers, ask it to describe them" pattern already proven in V1's AI Analyst, applied to profiling instead of a query result |

This entire section extends `app/analytics/profiling.py` — no new engine,
no new dependency, and (correlation analysis aside) no DuckDB needed. It's
listed after the SQL/dashboard work in priority because it improves
*existing* features' quality rather than adding a new capability, but it's
low-risk and high-portfolio-value work that could reasonably be pulled
earlier if the SQL layer turns out to be more work than expected.

---

## Where to look next

- Entities and relationships: `docs/V2_DATABASE_PLAN.md`
- How the system's shape changes: `docs/V2_ARCHITECTURE.md`
- Phases, files affected, risks, testing: `docs/V2_IMPLEMENTATION_PLAN.md`
- Priority table and role-focused reasoning: `docs/V2_FEATURES.md`
