# Learning Log

One section per `docs/PHASES.md` Phase 8 step: what was built, why this
approach over the alternatives considered, and interview questions to be
ready for. Written as each step ships, not retroactively — see
`docs/PROGRESS.md` for the dated build log this summarizes.

---

## Step 1 — Wire `/analyze` into the frontend

### What was built

The AI Analysis page switched from calling the old single-query `/ask`
endpoint to the hybrid, tool-grounded `/analyze` engine, with a new
"evidence panel" showing which of the 16 tools ran, a per-finding
verified/unverified indicator, and clear banners for a `degraded` status,
a clarification request, or warnings. `/ask` was kept fully working
behind an env-var feature flag rather than deleted. Alongside this, a
frontend test stack (Vitest + Testing Library + jsdom) was set up from
scratch — the repo had zero frontend tests before this step — with 12
tests covering the new view, plus 2 new backend regression tests proving
a tool error and a degraded status survive real HTTP serialization.

### Why this approach over the alternatives

**Feature flag over a hard cutover.** The alternative was to just delete
`/ask` and the old page code once `/analyze` worked. Rejected because
`/analyze` has a real, known gap today (no insight/dashboard saving —
see below) that `/ask` doesn't have, so a hard cutover would have been a
regression for that one workflow, not a pure improvement. A flag makes
the migration reversible per-deployment with zero code change, and keeps
the "old path still exists and still works" claim honest and testable
rather than aspirational.

**Flagging unverified findings instead of hiding them.** The answer
validator (built in Phase 7) already refuses to silently trust an
unmatched finding — it marks it `verified: false` and downgrades
confidence rather than deleting it. The frontend had to make the same
choice: hide unverified findings (cleaner-looking UI, but throws away a
signal the backend went out of its way to compute) or show them flagged.
Hiding was rejected because it would make the *validator itself*
pointless from the user's perspective — the whole point of validating is
to surface disagreement, not launder it away.

**Vitest + Testing Library over Playwright/Cypress for "frontend and
end-to-end tests."** The plan asked for both. A real browser-automation
E2E suite (Playwright) would drive the actual rendered app end-to-end
through a real browser, which is strictly more real — but it also needs
browser binaries, a running dev server, and meaningfully more setup than
this environment/step warranted for one page's test coverage. The
chosen middle ground: component tests that mock only the network
boundary (`apiClient.get`/`post`), exercising the real React Query
hooks, the real component tree, and real user interactions
(`@testing-library/user-event`) — plus backend tests proving the exact
HTTP response shape the frontend depends on. This covers the actual
regression risk (does the UI correctly render every response shape the
backend can send?) without the infrastructure cost of a full browser
suite. Trade-off made explicitly, not by default: a true click-through
in a real browser hasn't happened this step (recorded as a known gap in
`docs/PROGRESS.md`), and Playwright is the natural next tool if/when
that's worth the setup cost.

**Not synthesizing a fake query to keep "Save insight" working.**
`InsightCreate`/`DashboardChartCreate` both require exactly one
`DatasetQueryRequest` + `row_count` (a NOT NULL column,
`backend/app/models/insight.py`). `/analyze` can run zero, one, or many
tool calls of different shapes in one answer. The tempting shortcut —
pick the first `group_by_aggregate` call, if any, and construct a query
from its arguments — was rejected because it would silently misrepresent
what was actually asked and answered; a saved insight is supposed to be
reproducible, and a synthesized query wouldn't reproduce the real
analysis. Left as an explicit, documented gap instead of a plausible-
looking but incorrect workaround.

### Interview questions to be ready for

1. **"Your AI Analyst validates its own answers — walk me through what
   happens when a finding fails validation. Why not just drop it?"**
   Be ready to explain `app/ai/answer_validator.py`'s behavior (mark
   `verified: false`, downgrade confidence, keep it) and the UI
   consequence (shown with a warning icon, not hidden), and why hiding
   would defeat the purpose of validating at all — a user should be able
   to see *that* the system caught something it couldn't confirm, not
   just get a shorter, falsely-confident list.
2. **"Why keep a deprecated endpoint (`/ask`) around instead of deleting
   it once you had something better?"** Be ready to name the concrete
   asymmetry that justified it (`/ask` still supports save-to-
   insight/dashboard, which `/analyze` doesn't yet), and the mechanism
   (an env var read once, at the top of the page component, not scattered
   conditionals) — and to say plainly that this is a temporary state
   tracked in `docs/PHASES.md`, not a permanent two-endpoint design.
3. **"You chose component tests with a mocked API over full E2E browser
   tests. What are you *not* catching by doing that, and how would you
   decide when it's worth adding Playwright?"** Be ready to name the real
   gap (CSS/layout regressions, real browser quirks, actual network
   timing, a genuine multi-page user journey) versus what the chosen
   approach does catch (every response shape rendering correctly, real
   component/hook wiring, real user-event interactions) — and a concrete
   trigger for reconsidering (e.g. once there's a second page depending
   on the same evidence panel, or before a real deploy where a visual
   regression would be user-facing).

---

## Step 2 — NL-to-SQL safety audit

### What was built

Two real, working validation bypasses in the NL-to-SQL/SQL Explorer
path were found by actually attacking the deployed validator/engine
with real payloads, not by reading the code and reasoning about it:
(1) bare function calls (`version()`, `current_database()`,
`current_setting(...)`) had no validation at all and executed
successfully; (2) a query specifying its own `LIMIT` bypassed the row
cap entirely, however large. Both fixed — the function gap by rejecting
`sqlglot`'s `exp.Anonymous` node class outright (every standard SQL
function gets its own named class; everything else falls back to
Anonymous, which covered every non-standard function tried with zero
hand-maintained allowlist), the limit gap by always clamping to
`min(requested, row_limit)`. Added `enable_external_access=false` on
the DuckDB connection as an independent second layer. Closed a real
test-coverage gap (query timeout had never been tested for the SQL
path) and a real ownership-test gap (`/ask-sql`'s only prior test used
a fake UUID, not a real dataset owned by someone else). Corrected the
same stale "no SQL/DuckDB in this codebase" claim in three different
docs (`ARCHITECTURE.md`, `AI_ANALYTICS.md`, `SECURITY.md`) that all
predated V2's NL-to-SQL shipping and were never updated afterward.

### Why this approach over the alternatives

**Attacking the real code over auditing by reading it.** The plan asked
for a "safety audit" — the tempting shortcut is to read
`sql_validator.py`, reason about what it does, and write down what
*should* be true. That's exactly how the two real gaps here survived
undetected through the original implementation and its own test suite:
the code's own docstring confidently asserted defense-in-depth that
didn't fully exist. Writing a standalone script that actually calls
`validate_and_prepare()` and `execute_sql()` with real attack payloads,
against the real installed `sqlglot`/`duckdb` versions, is the only way
that gap gets caught — reasoning about code can miss what code actually
does; running it can't.

**Rejecting `exp.Anonymous` over hand-writing a function allowlist.**
The obvious first instinct for "block dangerous functions" is a
blocklist (`version`, `current_database`, `read_text`, ...) or an
allowlist (`SUM`, `AVG`, `COUNT`, ...) maintained by hand. Both were
rejected once inspecting `sqlglot`'s actual parse output showed every
standard SQL function already gets its own specific AST class — meaning
`exp.Anonymous` *is* an implicit "unrecognized function" signal for
free, with no list to keep in sync as DuckDB adds functions or as new
extensions become autoloadable (confirmed live: this DuckDB version has
`autoload_known_extensions=true` by default, meaning a function
belonging to an extension can become available with no explicit
`INSTALL`/`LOAD` statement at all — a hand-written allowlist would need
to anticipate that; rejecting Anonymous doesn't need to).

**`enable_external_access=false` as defense-in-depth, not a
replacement for the validator.** Once the validator correctly rejected
every attack tried, the temptation is to stop there. The DuckDB
connection setting was added anyway, verified live to still allow the
one legitimate operation (querying the registered in-memory table) while
independently blocking filesystem/network functions — because the
validator's own docstring already states this codebase's philosophy
("defense in depth, not a single check," `docs/V2_ROADMAP.md`), and a
single layer that's *currently* correct is still one bug away from not
being. A second, structurally different layer (an engine-level
permission flag, not another AST check) doesn't share the same failure
mode as the first.

**Fail-safe over fail-open for an unparseable `LIMIT`.** `LIMIT 1+1` is
valid SQL but not a plain integer literal this code can read directly.
The easy-but-wrong choice: if it can't be parsed as a number, leave it
alone (fail-open, trusting the original query). Chosen instead: treat
"couldn't confidently parse this as a small number" the same as
"absent," and clamp it — consistent with the rest of this validator's
posture (reject/clamp what can't be verified, never assume it's safe by
default).

### Interview questions to be ready for

1. **"Walk me through the two SQL validation bugs you found. Why did
   the existing table/column checks not catch a bare function call like
   `version()`?"** Be ready to explain the actual AST shape: `exp.Table`
   and `exp.Column` are specific node types the original checks
   `find_all()`'d for, but a function call is neither — it's its own
   node (`exp.Anonymous` for unrecognized ones), which nothing was
   walking the tree looking for at all. The bug wasn't a broken check;
   it was a category of node no check ever looked at.
2. **"You added `enable_external_access=false` after the validator was
   already fixed. Wasn't that redundant?"** Be ready to explain defense-
   in-depth as a stance, not a checklist item — a second, independently-
   reasoned layer only pays off exactly when the first one has a bug
   neither of us has found yet, which is the whole point; explain the
   concrete verification (it didn't break the real table, it did block
   `read_csv` even when called directly, bypassing the validator
   entirely).
3. **"How do you know you found all the SQL injection bugs, not just
   two of them?"** Be ready to answer this honestly, not defensively —
   the audit found what it specifically tried (function calls, limit
   bypass) and fixed those; it explicitly does *not* claim completeness
   (see `docs/SECURITY.md`'s "What this audit did not find"). Be ready
   to name what a more thorough pass would add: fuzzing, a wider payload
   corpus, a second reviewer, and ongoing attention as DuckDB/sqlglot
   versions change what `exp.Anonymous` actually catches.

---

## Step 3 — Evaluation harness

### What was built

51 questions across 2 deterministically-generated sample datasets
(e-commerce orders, employee records — both with deliberately injected
duplicates, missing values, out-of-range values, and a formula
mismatch), covering all 16 analytical tools, the Natural Language to SQL
path, and 4 genuinely multi-step questions. Ground truth for every
question is computed by calling this project's own real `app.ai.tools`
functions directly — never a hand-rolled second implementation.
`evals/runner.py` drives each question through the real, live
Groq-backed pipeline (not a scripted/mocked provider — see the
trade-off below), scores the response, and records tool-selection
accuracy, value accuracy, the answer validator's intervention rate, and
real token/latency numbers pulled straight off Groq's own API response,
via an external instrumentation layer that patches the shared Groq
client with no change to any production code. Full numbers:
`docs/EVALS.md`.

### Why this approach over the alternatives

**Live Groq calls over a scripted/mocked provider.** The existing unit
tests (`tests/test_analyst_engine.py`) already prove the tool-calling
*loop's logic* is correct given a scripted provider's canned responses.
An eval whose provider is also scripted would only re-prove that same
logic — it structurally cannot answer "does the real model pick the
right tool and get the right number for a real question," which is the
actual thing worth measuring here. The cost of that choice is real: live
calls are slow, rate-limited (Groq's free tier — 8000 TPM, hit
repeatedly during this project's own earlier testing, `docs/BUGS.md`),
and non-deterministic run to run. Accepted deliberately, with pacing
(`--sleep`) and per-question failure isolation (one provider failure
never aborts the whole run) as the mitigation, not a workaround that
quietly makes the eval fake again.

**Ground truth from the app's real tools, not a second implementation.**
The tempting alternative — write eval-only code that independently
computes "the median revenue" or "how many outliers" — was rejected
because any drift between that second implementation and the app's real
one (e.g. a slightly different IQR multiplier) would silently produce a
*wrong* ground truth that the eval would then trust completely. Calling
`app.ai.tools` directly means the eval can only ever be checking
"did the model use these tools and report their real output correctly,"
which is exactly what needs checking — never "did we reinvent outlier
detection and land on the same formula twice."

**External instrumentation over changing `AnalyzeResponse`'s schema.**
Getting real token counts could have meant adding a `usage` field to
`AnalyzeResponse` and threading it through `analyst_engine.run_analysis`
— a public API schema change for every caller, for a need that's
specific to this eval harness (and, later, Step 4's cost logging).
Instead, `app.ai.groq_client.get_groq_client()`'s single shared,
cached client instance is patched externally, once, in
`evals/instrumentation.py` — every AI code path (`/analyze`, the legacy
`/ask`, NL-to-SQL) already funnels through that one object, so this
captures usage for all three with zero lines changed under
`backend/app/`. `ProviderMessage` did still gain a small, optional
`usage` field (`app/ai/providers/base.py`) as part of this step — that
one *is* production code, but it's additive (defaults to `None`,
nothing existing reads or requires it) and directly reusable by Step 4's
real per-request cost logging, rather than eval-only scaffolding that
would need rebuilding later.

**A regex/tolerance value-matcher over an LLM-as-judge grader.** Using a
second AI call to grade whether an answer is "correct" was considered
and rejected for this step: it would make the eval's own correctness
depend on the same class of system it's trying to evaluate, adds cost
and latency to every single question, and produces a grade that's
harder to audit than "here are the literal numbers extracted from the
text and the tolerance they were checked against." A plain
regex-extraction-plus-tolerance matcher is weaker (documented
explicitly in `docs/EVALS.md`'s Methodology section — it can miss a
correctly-phrased answer or accept a coincidental number) but every
scoring decision it makes is inspectable in the raw results file, which
matters more for a portfolio project meant to be defended in an
interview than a marginally smarter but opaque grader would.

### Interview questions to be ready for

1. **"Your eval harness makes real, live LLM calls instead of mocking
   the provider. Isn't that flaky and expensive — why not mock it like
   your unit tests do?"** Be ready to explain the difference in what
   each is actually testing (engine logic vs. real model behavior), and
   the concrete mitigations for flakiness/cost (pacing, per-question
   isolation, a `--limit` flag for a cheap smoke test before committing
   to a full paced run).
2. **"How do you compute 'ground truth' for a question like 'is this
   revenue outlier a real order or bad data' — that's not a single
   number?"** Be ready to explain that multi-step questions still pin a
   single, checkable fact (e.g. which specific order/record the
   investigation should surface) even when the full answer is
   necessarily prose — and to be honest that the free-text matcher is a
   heuristic, not a semantic grader, exactly as stated in
   `docs/EVALS.md`.
3. **"What's a concrete number this eval found that surprised you, and
   what would you do about it?"** Answer from the real, committed
   `docs/EVALS.md` results at the time of the interview — this is the
   one question on this list whose answer must come from that file, not
   from memory of what was expected going in.
