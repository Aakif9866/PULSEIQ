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
