# evals/

The AI Analyst evaluation harness — docs/PHASES.md Phase 8, step 3. Full
methodology and results: [`docs/EVALS.md`](../docs/EVALS.md).

| File | Purpose |
|---|---|
| `build_datasets.py` | Deterministically generates the 2 sample datasets in `datasets/` (fixed seed — re-running reproduces them byte-for-byte) |
| `datasets/` | The generated CSVs the eval questions run against |
| `ground_truth.py` | Computes every question's expected value by calling this project's real `app.ai.tools` functions directly (pure Polars, no LLM) |
| `eval_questions.py` | The 51-question set — all 16 tools, NL-to-SQL, multi-step questions |
| `instrumentation.py` | Captures real token usage/latency from Groq's API responses, for any AI code path, with no change to `backend/app/` |
| `runner.py` | Drives every question through the real, live pipelines and scores the responses |
| `results/` | Raw JSON output of actual runs — the evidence behind every number in `docs/EVALS.md` |

## Running it

```bash
cd backend && pip install -r requirements-dev.txt   # if not already
python ../evals/build_datasets.py
python ../evals/runner.py --sleep 30                  # full run
python ../evals/runner.py --limit 5 --sleep 10         # quick smoke test
```

Needs a real `GROQ_API_KEY` (`AI_PROVIDER=groq` in `.env`) — this makes
real, quota-consuming API calls on purpose (see `docs/EVALS.md`).
