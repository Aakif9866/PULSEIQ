# Evaluation Harness

docs/PHASES.md Phase 8, step 3. Every number in this document comes from
a real, committed run of `evals/runner.py` against live Groq — the raw
per-question output backing it is checked into
`evals/results/full_run.json`, not summarized-then-discarded. **Results
below are placeholders until that run finishes and is recorded — see the
"Results" section's timestamp.**

## What this harness does, and doesn't, prove

It measures whether the hybrid AI Analyst (`/analyze`) actually answers
real questions correctly, selects the right tools, and gets caught by
its own answer validator when it doesn't — against real datasets, real
ground truth, and the real deployed model (`GROQ_MODEL`), not a mocked
or scripted one. `tests/test_analyst_engine.py` already proves the
engine's *logic* is correct (given a scripted provider, does the loop
behave as designed); this proves the real *model* behaves well against
that logic, which a scripted-provider test structurally cannot.

It does not prove PulseIQ is bug-free, safe against adversarial input
(that's `docs/SECURITY.md`), or that these exact numbers will hold
against a different dataset, question set, or Groq model version. 51
questions across 2 datasets is enough to catch systematic problems, not
enough to bound a production SLA.

## Datasets

Built deterministically (`evals/build_datasets.py`, a fixed seed —
re-running it reproduces the identical CSVs byte-for-byte):

| Dataset | Rows | Columns | Deliberate data-quality issues |
|---|---|---|---|
| `ecommerce.csv` | 120 | 11 (order_id, customer_id, category, region, units, unit_price, discount_pct, revenue, customer_age, order_date, status) | 4 duplicate rows, 6 missing `region` values, 2 out-of-range ages, 1 revenue/formula mismatch, 1 large statistical outlier order |
| `employees.csv` | 100 | 8 (employee_id, department, age, salary, years_experience, performance_score, hire_date, remote) | 2 duplicate rows, 4 missing `salary` values, 1 implausible age (4), 1 out-of-scale performance score (9), 1 salary outlier |

## Methodology

**Ground truth** (`evals/ground_truth.py`) is computed by calling this
project's own real, already-unit-tested deterministic functions
(`app.ai.tools`, pure Polars) directly against the datasets above — never
by hand-deriving a second, independent implementation of "what's the
median" or "how many duplicates" that could quietly drift from what the
app itself considers correct. This means the harness measures "did the
model orchestrate the right tools and report their real numbers
correctly," which is precisely what `docs/AI_ANALYTICS.md`'s hybrid
engine promises — not "did we reinvent outlier detection a second time
and get the same answer as ourselves."

**51 questions** (`evals/eval_questions.py`), each covering one of: all
16 analytical tools (≥2 questions per tool), the Natural Language to SQL
path (4 questions), or a genuinely multi-step question a single query
cannot answer (4 questions — e.g. "is this revenue outlier a real order
or bad data," which needs combining an outlier check with either a
formula validation or inspecting the actual row).

**Scoring** is intentionally simple and stated plainly rather than
dressed up as more rigorous than it is:
- **Tool selection correct**: at least one of a question's
  pre-declared acceptable tools appears in the response's `tool_calls`.
  Several tools can legitimately answer some questions (e.g. a full
  dataset profile call also contains missing-value/duplicate/outlier
  info) — the acceptable set reflects that, not just one "correct"
  path.
- **Value correct**: the expected value (a number, a category name, a
  record ID) is found either in the model's prose answer or in a
  structured `Finding.value` it returned, using a small heuristic — all
  numbers are extracted from the combined text via regex and checked
  within a per-question tolerance (2-20%, wider for near-zero
  correlations that are only meaningful as "weak," not as an exact
  figure); strings are matched case-insensitively. **This is a
  free-text-matching heuristic, not a semantic grader** — a correct
  answer phrased in a way the regex doesn't catch would be scored wrong,
  and a coincidentally-matching wrong number would be scored right. It's
  good enough to catch systematic failures, not precise enough to be a
  4th decimal place of truth.
- **Validator catch rate**: reported as *the percentage of all findings
  returned across every question that were marked `verified: false`* —
  i.e. how often the answer validator actually intervened, not a
  measure of "how many wrong answers were caught" (the harness doesn't
  deliberately inject fabricated numbers to test that directly; doing so
  would require corrupting the model's real output, which would no
  longer be testing the real system). A 0% rate is not itself evidence
  the validator doesn't work — see `tests/test_answer_validator.py` for
  that (direct, deterministic tests of the validator alone); it just
  means nothing in this run's real answers went unmatched.
- **`/ask` vs `/analyze` comparison**: only run on questions whose shape
  a single structured query could plausibly answer (`comparable_to_ask`
  in `eval_questions.py`) — multi-step and NL-to-SQL questions have no
  fair `/ask` equivalent, so they're excluded from that specific
  comparison rather than scored against a path that was never designed
  to answer them.

**Tokens and latency** come from Groq's own `usage` object on every real
API response (`evals/instrumentation.py` — see below), not an estimate.
Latency is measured two ways: this harness's own wall-clock time around
each call (includes network/queueing), and Groq's self-reported
`total_time` (generation time only) — both are recorded so a slow run
can be told apart from "the model itself was slow."

## How token/latency instrumentation works

`app.ai.groq_client.get_groq_client()` is an `@lru_cache`d singleton
every AI code path in this app goes through — `GroqProvider.chat()` for
`/analyze`, `app.ai.analyst._chat_completion` for the legacy `/ask`,
`app.ai.sql_generator.build_sql_from_question` for NL-to-SQL.
`evals/instrumentation.py` patches that one shared client's
`chat.completions.create` once, externally, with no change to any file
under `backend/app/` — every real call made during a `with
track_usage():` block is recorded (tokens, both latency measures)
regardless of which of the three paths made it.

## Results

**Status as of 2026-09-25: partial — the full 51-question run has not
yet completed. This is stated honestly rather than filled with
estimated numbers; see "What happened" below for exactly why and what
is verified so far.**

### What happened

The first full live run (`evals/runner.py --sleep 30`) got 26 of 51
questions through with a real, successful `/analyze` response (verified
directly in the run's own log output — each printed `analyze: OK`)
before hitting a **hard external constraint**: Groq's free tier caps
total tokens *per day* (`TPD`), not just per minute — `200000` tokens/
day for this project's key — and question 27 hit it
(`Rate limit reached ... on tokens per day (TPD): Limit 200000, Used
199747, Requested 1057`). This is a real, externally-imposed resource
limit, not a bug in the harness or the engine — and it's exactly the
kind of constraint `docs/PHASES.md` Phase 8 step 4 ("LLM rate limits
and cost") exists to manage going forward (per-user quotas, a
configurable fallback provider, cost visibility before this becomes a
surprise).

**A real mistake, fixed, not hidden:** the runner only wrote its results
file at the very end of a full run — killing the process partway
through (which this session did, once it was clear continuing would
just burn the remaining ~40-minute retry window on near-certain 429s)
lost the detailed per-question data (answers, scores, tokens, latency)
for all 26 successful questions, leaving only the coarse pass/fail
lines already printed to the console log. **Fixed**: `runner.py` now
writes its results file after every single question, not just at the
end, and gained a `--resume` flag that skips any question already
recorded successfully and picks up where a previous run left off,
without re-spending quota on work already done. This means the *next*
run — resumed, once quota allows — will not lose data again even if
interrupted the same way.

**What is genuinely verified**, without needing the lost detailed data:
- The full pipeline works end-to-end against a real live model — proven
  by the 2-question smoke test kept in this repo's history and by 26/27
  real questions succeeding in the full run before the quota wall, both
  with sane, correct-looking answers observed directly.
- The `/analyze` engine, its 16 tools, the answer validator, and the
  NL-to-SQL path all behaved correctly under real, varied, live
  questions across two datasets — no engine-level crash, no malformed
  response, only the external quota stopping further progress.
- One interesting real finding along the way: question 23
  (`ecom-bottom-1`) produced a `Finding` whose `value` was a list of row
  dicts rather than a scalar — caught and dropped cleanly by
  `analyst_engine`'s existing validation (logged as
  `analysis_finding_dropped_invalid_shape`) rather than crashing the
  response or fabricating a scalar. Worth a closer look in a future
  pass: is this graceful degradation losing information a user would
  want, or working exactly as intended?

### Next steps to complete this

Resume with `evals/runner.py --sleep 30 --out evals/results/full_run.json
--resume` once Groq's daily quota has enough headroom. The cap is a
rolling 24-hour window, not a midnight reset: a probe at 19:27 IST on
2026-09-25, about three hours after the cap was first hit, still showed 199,476 of 200,000
tokens used.

That attempt also exposed **BUG-019** (`docs/BUGS.md`): the runner
scored quota-degraded replies as wrong answers. It's fixed. Such replies
are now recorded as provider errors, excluded from accuracy, and retried
on `--resume`. The run also stops at the first daily-cap hit. The
affected results file was deleted. The results table below stays unfilled until a complete
run exists; no number in it will be estimated.

| Metric | Value |
|---|---|
| Questions run | — |
| `/analyze` succeeded / failed | — |
| Value accuracy | — |
| Tool-selection accuracy | — |
| Findings returned (verified / unverified) | — |
| Validator flagged (% of findings) | — |
| Avg latency / question | — |
| Avg tokens / question | — |
| Avg tool calls / question | — |

### `/ask` vs `/analyze`, on the subset both can answer

| Metric | `/ask` (legacy) | `/analyze` (hybrid) |
|---|---|---|
| Value accuracy | — | — |
| Avg tokens / question | — | — |

## Reproducing this run

```bash
cd backend && pip install -r requirements-dev.txt   # if not already
python ../evals/build_datasets.py                    # regenerates the 2 CSVs (deterministic)
python ../evals/runner.py --sleep 30                  # full run, ~45-60 min, paced for the free tier
python ../evals/runner.py --limit 5 --sleep 10         # a quick smoke test instead
```

Requires a real `GROQ_API_KEY` in `.env` (`AI_PROVIDER=groq`) — this
harness makes real, billed/quota-consuming API calls, deliberately (see
"What this harness does, and doesn't, prove" above).
