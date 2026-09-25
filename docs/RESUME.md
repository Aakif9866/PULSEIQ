# Resume material — PulseIQ

For a 1–2 years-of-experience software engineer. Every number below is a
real count or measurement from this repository; the table at the end says
where each one comes from, so it can be defended in an interview.

## One-line description

**PulseIQ** — a full-stack analytics web app where users upload data and
ask questions in plain English, answered by verified tool computations
rather than language-model guesses.

## Resume bullets

- Built an artificial intelligence (AI) data analyst where a large language model (LLM) chooses among 16 deterministic tools and a validator checks each finding.
- Secured natural-language-to-SQL (Structured Query Language) generation with syntax-tree validation and a sandboxed DuckDB engine; adversarial testing found and fixed 2 validator bypasses.
- Created a 51-question evaluation harness scoring tool selection, answer accuracy, and token cost against ground truth computed by deterministic code, not the model.
- Shipped rate-limit handling, answer caching, and per-user token quotas, backed by 316 backend and 24 frontend tests in continuous integration (CI).

**Alternate** (swap in for a role that emphasizes reliability/operations):

- Traced requests end to end with OpenTelemetry and request identifiers, exposing an outage-handling bug that returned misleading errors and had evaded unit tests.

## 30-second interview pitch

> PulseIQ lets someone upload a spreadsheet and ask questions about it in
> plain English. The interesting part is that the language model never
> calculates anything. It only decides which of sixteen analysis tools to
> run, the tools compute the real numbers, and a validator checks every
> finding against the tools' actual output before the user sees it. I also made the
> text-to-SQL feature safe by parsing every query into a syntax tree, then
> attacked my own validator and found two real bypasses, which I fixed.
> And it's deployed, with a live demo.

## Where every number comes from

| Number | Claim | Source |
|---|---|---|
| 16 | analytical tools | `backend/app/ai/tool_specs.py` (`TOOL_SPECS`) |
| 2 | SQL validator bypasses found and fixed | `docs/BUGS.md` BUG-014, BUG-015; `docs/SECURITY.md` |
| 51 | evaluation questions | `evals/eval_questions.py` (CI asserts ≥ 50) |
| 316 / 24 | backend / frontend tests | `pytest` / `vitest` runs at the Phase 8 step 6 commit |
| 1 | outage-handling bug found via tracing | `docs/BUGS.md` BUG-017 |

**Numbers deliberately not claimed:** answer accuracy and validator catch
rates. The full evaluation run stopped at Groq's free-tier daily token
limit (`docs/EVALS.md`), and a percentage from 26 questions would be
presenting a partial run as a result. Add them only once a complete run
exists.
