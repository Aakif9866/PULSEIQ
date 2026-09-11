# PulseIQ V2 — Feature Prioritization

**Mostly planning, with one feature now implemented.** Priorities below are
judged against four audiences at once — Software Engineering, Data
Analyst, Data Engineering, and AI/ML-adjacent roles — since a portfolio
project's value depends heavily on who's reviewing it. A feature scoring
high for one audience and low for others is called out explicitly rather
than averaged away.

## Prioritization table

| Feature | User Value | Technical Complexity | Portfolio Value | Priority |
|---|---|---|---|---|
| **AI Anomaly Monitoring / Data Pulse** | High — a fundamentally different capability (proactive, not reactive); "tell me when something matters" instead of "answer what I asked" | Medium-High (a real deterministic-engine-plus-AI-explanation architecture, plus alerting) | Very High — a distinct product story from every other V2 feature, and a clean demonstration of "AI explains, code decides" | **P0 — IMPLEMENTED** |
| Natural Language to SQL (+ validation layer) | High — unlocks real analytical questions the current schema can't express | High | Very High — the strongest "I understand security tradeoffs" story in this entire roadmap | **P0** |
| SQL Explorer + Query History | Medium-High — power users get direct control; everyone gets memory | Medium | High — demonstrates full-stack feature ownership (new tables, new endpoints, new UI) | **P0** |
| Persistent Object Storage (R2 in production) | High — fixes a real, currently-documented limitation | Low-Medium (code exists, mostly verification) | Medium — important for *credibility* ("is this actually production-ready?") more than for demonstrating a new skill | **P0** |
| More chart types + multiple dashboards + reorder | Medium — visibly improves the product | Low-Medium | Medium-High — dashboards are the most demo-able part of any analytics portfolio project | **P1** |
| AI Visualization Intelligence (rules-table based) | Medium — a nice "it feels smart" touch | Low-Medium | High for AI/ML-adjacent roles specifically — shows judgment about *when not* to use an LLM | **P1** |
| Data Quality and Profiling | Medium — genuinely useful, but less visible/demo-able than SQL or dashboards | Low-Medium | High for Data Analyst / Data Engineer roles specifically | **P1** |
| Dashboard resize + filters + saved layout | Medium | Medium-High | Medium — polish on top of P1's dashboard work, not a new capability | **P2** |
| Dataset versioning | Low-Medium — real but not urgent for a single-user-per-dataset workflow | Medium-High (changes what `Dataset` means) | Low-Medium — a reasonable "V3" idea, not essential to demonstrate V2's core thesis | **P2 / defer** |
| Cross-filtering, freeform drag-and-drop dashboard layout | High if built well | High | Medium — impressive in a demo, but disproportionate effort relative to what it proves beyond "resize/filters" already proves | **Future work, not V2** |

## Recommended implementation order

**As originally reasoned** (before Anomaly Monitoring existed), assuming
work proceeds strictly in order of what extends the current query-layer
strength most directly:

1. **Natural Language to SQL** (Phase 1) — the roadmap's centerpiece;
   everything else in P0/P1 either depends on it (SQL Explorer) or is
   independent of it (storage, dashboards, profiling) and could in principle
   be reordered, but this is the feature that changes what PulseIQ *is*.
2. **SQL Explorer + Query History** (Phase 2) — directly extends #1; doing
   it immediately after means the SQL validation layer gets a second,
   different caller quickly, which is exactly how you find out if it was
   built generally enough.
3. **Persistent Object Storage** (Phase 7) — reordered ahead of the
   dashboard/profiling work here because it's the one item that's arguably
   *not a new feature at all* but a correctness fix to something already
   claimed as "done" (a `StorageProvider` abstraction exists specifically so
   this swap requires no new code) — low effort, meaningfully raises
   production credibility.
4. **Dashboard: chart types, reorder, multiple dashboards** (Phase 3) — the
   most visibly "the product got better" change, good to ship once the
   riskier SQL work is stable.
5. **AI Visualization Intelligence** (Phase 5) — benefits from #4's chart
   types already existing, and is relatively cheap given the deliberately
   non-AI-heavy rules-table design.
6. **Data Quality and Profiling** (Phase 6) — independent of everything
   above; could genuinely be done in parallel with 3-5 if working on both
   backend and frontend concerns at once.
7. **Dashboard: resize, filters** (Phase 4) — the more effortful dashboard
   polish, once the simpler dashboard work has proven out.
8. **Dataset versioning** — explicitly deferred; revisit only if V2's other
   phases reveal it's actually blocking something, not on schedule.

**As actually executed**: **AI Anomaly Monitoring** was built first, ahead
of this list, by direct request. Re-evaluating that choice honestly rather
than rationalizing it after the fact: it was a *defensible* reordering, not
just an expedient one — it has zero dependency on anything above (no
DuckDB, no shared code path with the SQL validation layer that doesn't
exist yet), so building it first didn't leave any of the P0/P1 reasoning
above stale or block any later phase. It also diversifies the portfolio
story — every other item on this list is still "a better way to query or
view data you already asked about"; Anomaly Monitoring is the one place
V2 does something the user didn't ask for in the moment. The rest of the
order above (Phases 1 → 2 → 7 → 3 → 5 → 6 → 4) remains the recommended
path for everything not yet built.

## Which feature would provide the biggest portfolio improvement

This now has two strong, different answers — presented honestly rather
than picking one to seem decisive:

**If judged on demonstrating engineering judgment about AI's proper role:**
**Natural Language to SQL, specifically because of its validation layer.**
V1's current safety story is "there's no SQL, so there's nothing to
sandbox" — true, but it's a story about *avoiding* a hard problem, not
*solving* one. Building a real SQL generation path with genuine parsing,
allow-listing, and bounded execution turns that into a story about
deliberately taking on a harder, riskier primitive and building real
safeguards around it. This is still the single hardest, most senior-sounding
piece of engineering *left to build* in this roadmap.

**If judged on what's already real, tested, and demoable today:** **AI
Anomaly Monitoring** — it's the one item in this entire table that moved
from a table row to working, tested code during this same task. It tells a
genuinely different product story (proactive vs. reactive) than everything
else here, and it demonstrates the *exact same* "AI explains, deterministic
code decides" discipline the NL-to-SQL section argues for — just already
built and verified with 44 passing tests, rather than argued for on paper.

Both conclusions stand together, not in competition: NL-to-SQL remains the
single highest-value thing left to build; Anomaly Monitoring is the single
highest-value thing already built.

## Which V2 feature should NOT be implemented yet

**Cross-filtering and freeform drag-and-drop dashboard layout.** Both are
called out in `docs/V2_ROADMAP.md` as "future work," not part of the six
implementation phases, for a specific reason: they add real frontend state
complexity (shared cross-widget filter state; a full grid-layout library
with drag/resize/persist) whose main payoff is *demo polish* rather than a
new underlying capability — Phase 3/4's simpler reorder-and-filter work
already proves the same architectural points (position/layout persistence,
filter application on stored queries) at a fraction of the effort. Building
the fancier version first would be exactly the kind of "impressive-sounding
but disproportionate" work this roadmap is explicitly trying to avoid.
Dataset versioning is a close second for the same reason — real value, but
it changes a core modeling assumption (`Dataset` = one file) for a benefit
that doesn't clearly justify that cost yet at this project's actual scale.
