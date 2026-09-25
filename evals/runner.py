"""Eval runner — docs/PHASES.md Phase 8 step 3. Drives every question in
eval_questions.py through the real, live Groq-backed pipelines (no
mocking of the AI provider — this is deliberately NOT the same thing as
tests/test_analyst_engine.py's scripted-provider tests, which check the
engine's logic; this checks the actual model's real behavior) and scores
each response against ground truth computed directly from app.ai.tools.

Usage:
    backend/.venv/bin/python evals/runner.py [--limit N] [--sleep SECONDS]
                                              [--skip-ask] [--out PATH]

Respects the free-tier Groq rate limit (8000 TPM, observed live during
this project's own testing — see docs/BUGS.md) by pacing one question at
a time with a configurable sleep, and by treating a provider failure on
one question as a recorded failure, never a crash of the whole run.
"""
import argparse
import json
import re
import sys
import time
import traceback
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

_BACKEND = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(_BACKEND))
sys.path.insert(0, str(Path(__file__).parent))

import polars as pl  # noqa: E402
from app.ai.analyst import build_query_from_question, summarize_result  # noqa: E402
from app.ai.analyst_engine import run_analysis  # noqa: E402
from app.ai.providers.groq_provider import GroqProvider  # noqa: E402
from app.ai.sql_generator import build_sql_from_question  # noqa: E402
from app.analytics.sql_engine import execute_sql  # noqa: E402
from app.analytics.sql_validator import validate_and_prepare  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.core.exceptions import AiResponseError, InvalidQueryError  # noqa: E402

from eval_questions import QUESTIONS, EvalQuestion  # noqa: E402
from ground_truth import ground_truth  # noqa: E402
from instrumentation import track_usage  # noqa: E402

settings.AI_PROVIDER = "groq"

_NUMBER_RE = re.compile(r"[-+]?\$?[\d,]*\.?\d+")


def _extract_numbers(text: str) -> list[float]:
    numbers = []
    for match in _NUMBER_RE.findall(text):
        cleaned = match.replace("$", "").replace(",", "")
        if cleaned in ("", "-", "+", "."):
            continue
        try:
            numbers.append(float(cleaned))
        except ValueError:
            continue
    return numbers


def _fake_dataset(df: pl.DataFrame):
    """A duck-typed stand-in for the ORM Dataset model — the legacy /ask
    and NL-to-SQL code paths only ever read .columns_profile/.row_count
    off it (verified by reading app/ai/analyst.py and sql_generator.py
    directly), never touch the database."""
    columns_profile = [{"name": name, "dtype": str(dtype)} for name, dtype in df.schema.items()]
    return SimpleNamespace(columns_profile=columns_profile, row_count=df.height)


def value_matches(expected, haystack: str, tolerance_pct: float) -> bool:
    if isinstance(expected, list):
        return all(value_matches(v, haystack, tolerance_pct) for v in expected)
    if isinstance(expected, bool):
        return str(expected).lower() in haystack.lower()
    if isinstance(expected, int | float):
        numbers = _extract_numbers(haystack)
        if expected == 0:
            return any(abs(n) < 1e-6 for n in numbers)
        tolerance = abs(expected) * (tolerance_pct / 100)
        return any(abs(n - expected) <= tolerance for n in numbers)
    return str(expected).lower() in haystack.lower()


def _score_analyze(question: EvalQuestion, response) -> dict:
    haystack = response.answer + " " + " ".join(str(f.value) for f in response.findings)
    tools_used = {tc.tool for tc in response.tool_calls}
    tool_correct = bool(tools_used & set(question.expected_tools))
    value_correct = value_matches(question.expected_value, haystack, question.tolerance_pct)
    return {
        "tool_correct": tool_correct,
        "tools_used": sorted(tools_used),
        "value_correct": value_correct,
        "status": response.status,
        "answer": response.answer,
        "findings_total": len(response.findings),
        "findings_verified": sum(1 for f in response.findings if f.verified),
        "findings_unverified": sum(1 for f in response.findings if not f.verified),
        "warnings": response.warnings,
    }


def _run_legacy_ask(question: EvalQuestion, df: pl.DataFrame) -> dict:
    from app.analytics.query_engine import run_query

    dataset = _fake_dataset(df)
    query = build_query_from_question(question.question, dataset)
    result = run_query(df, query, row_limit=settings.QUERY_ROW_LIMIT)
    answer = summarize_result(question.question, result)
    haystack = answer + " " + json.dumps(result.rows, default=str)
    value_correct = value_matches(question.expected_value, haystack, question.tolerance_pct)
    return {"value_correct": value_correct, "answer": answer}


def _run_nl_to_sql(question: EvalQuestion, df: pl.DataFrame) -> dict:
    dataset = _fake_dataset(df)
    raw_sql = build_sql_from_question(question.question, dataset, df)
    known_columns = {c["name"] for c in dataset.columns_profile}
    safe_sql = validate_and_prepare(
        raw_sql, table_name="dataset", allowed_columns=known_columns,
        row_limit=settings.QUERY_ROW_LIMIT,
    )
    result = execute_sql(df, safe_sql)
    answer = summarize_result(question.question, result)
    haystack = answer + " " + json.dumps(result.rows, default=str)
    value_correct = value_matches(question.expected_value, haystack, question.tolerance_pct)
    return {"value_correct": value_correct, "answer": answer, "generated_sql": safe_sql}


def run_one(question: EvalQuestion) -> dict:
    df = ground_truth(question.dataset).df
    entry: dict = {"id": question.id, "dataset": question.dataset, "question": question.question,
                    "category": question.category, "expected_value": question.expected_value,
                    "value_description": question.value_description}

    # --- /analyze (the hybrid engine — every question goes through this) ---
    start = time.perf_counter()
    try:
        with track_usage() as usage:
            response = run_analysis(df, GroqProvider(), question.question)
        entry["analyze"] = {
            **_score_analyze(question, response),
            "latency_ms": round((time.perf_counter() - start) * 1000),
            "total_tokens": usage.total_tokens,
            "call_count": usage.call_count,
            "groq_reported_ms": round(usage.groq_reported_ms),
        }
    except (AiResponseError, InvalidQueryError) as exc:
        elapsed_ms = round((time.perf_counter() - start) * 1000)
        entry["analyze"] = {"error": str(exc), "latency_ms": elapsed_ms}
    except Exception as exc:  # noqa: BLE001 - one question's failure must never abort the run
        entry["analyze"] = {
            "error": f"{type(exc).__name__}: {exc}", "traceback": traceback.format_exc()
        }

    # --- NL-to-SQL (only the questions specifically testing that path) ---
    if question.category == "nl_to_sql":
        start = time.perf_counter()
        try:
            with track_usage() as usage:
                nl_result = _run_nl_to_sql(question, df)
            entry["nl_to_sql"] = {
                **nl_result,
                "latency_ms": round((time.perf_counter() - start) * 1000),
                "total_tokens": usage.total_tokens,
            }
        except Exception as exc:  # noqa: BLE001
            entry["nl_to_sql"] = {"error": f"{type(exc).__name__}: {exc}"}

    # --- legacy /ask comparison, only where the question shape allows it ---
    if question.comparable_to_ask:
        start = time.perf_counter()
        try:
            with track_usage() as usage:
                ask_result = _run_legacy_ask(question, df)
            entry["ask"] = {
                **ask_result,
                "latency_ms": round((time.perf_counter() - start) * 1000),
                "total_tokens": usage.total_tokens,
            }
        except Exception as exc:  # noqa: BLE001
            entry["ask"] = {"error": f"{type(exc).__name__}: {exc}"}

    return entry


def _avg(values: list[float], ndigits: int = 0) -> float | None:
    return round(sum(values) / len(values), ndigits) if values else None


def summarize(results: list[dict]) -> dict:
    analyzed = [r["analyze"] for r in results if "error" not in r.get("analyze", {})]
    failed = [r for r in results if "error" in r.get("analyze", {})]
    tool_applicable = [
        r for r in results
        if r["category"] != "nl_to_sql" and "error" not in r.get("analyze", {})
    ]

    findings_total = sum(a.get("findings_total", 0) for a in analyzed)
    findings_unverified = sum(a.get("findings_unverified", 0) for a in analyzed)

    ask_pairs = [
        r for r in results
        if "ask" in r and "error" not in r.get("ask", {}) and "error" not in r.get("analyze", {})
    ]

    def pct(n, d):
        return round(100 * n / d, 1) if d else None

    return {
        "total_questions": len(results),
        "analyze_succeeded": len(analyzed),
        "analyze_failed": len(failed),
        "analyze_value_accuracy_pct": pct(
            sum(1 for a in analyzed if a.get("value_correct")), len(analyzed)
        ),
        "analyze_tool_selection_accuracy_pct": pct(
            sum(1 for r in tool_applicable if r["analyze"].get("tool_correct")),
            len(tool_applicable),
        ),
        "validator_flagged_pct_of_findings": pct(findings_unverified, findings_total),
        "findings_total": findings_total,
        "findings_unverified": findings_unverified,
        "avg_latency_ms": _avg([a.get("latency_ms", 0) for a in analyzed]),
        "avg_tokens_per_question": _avg([a.get("total_tokens", 0) for a in analyzed]),
        "avg_tool_calls_per_question": _avg([a.get("call_count", 0) for a in analyzed], 1),
        "ask_vs_analyze_comparable_questions": len(ask_pairs),
        "ask_value_accuracy_pct": pct(
            sum(1 for r in ask_pairs if r["ask"].get("value_correct")), len(ask_pairs)
        ),
        "analyze_value_accuracy_on_comparable_subset_pct": pct(
            sum(1 for r in ask_pairs if r["analyze"].get("value_correct")), len(ask_pairs)
        ),
        "ask_avg_tokens": _avg([r["ask"].get("total_tokens", 0) for r in ask_pairs]),
        "analyze_avg_tokens_on_comparable_subset": _avg(
            [r["analyze"].get("total_tokens", 0) for r in ask_pairs]
        ),
    }


def _write_results(out_path: Path, results: list[dict]) -> None:
    """Called after every single question, not just at the end — a run
    killed partway through (rate limits, a crash, an interrupted
    session) previously lost every result still only held in memory;
    this makes that no longer possible. See docs/PROGRESS.md: a real,
    partial-results-lost incident during the Phase 8 step 3 live run is
    exactly what motivated this."""
    summary = summarize(results)
    payload = json.dumps({"summary": summary, "results": results}, indent=2, default=str)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(payload)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--sleep", type=float, default=15.0)
    parser.add_argument("--skip-ask", action="store_true")
    parser.add_argument("--out", type=str, default=None)
    parser.add_argument(
        "--resume", action="store_true",
        help="Skip any question id already present (with no error) in --out, "
        "and append to its existing results instead of starting over.",
    )
    args = parser.parse_args()

    out_path = Path(args.out) if args.out else Path(__file__).parent / "results" / (
        f"run_{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.json"
    )

    questions = QUESTIONS[: args.limit] if args.limit else QUESTIONS
    if args.skip_ask:
        for q in questions:
            q.comparable_to_ask = False

    results: list[dict] = []
    if args.resume and out_path.exists():
        previous = json.loads(out_path.read_text())
        results = previous.get("results", [])
        already_ok = {r["id"] for r in results if "error" not in r.get("analyze", {})}
        questions = [q for q in questions if q.id not in already_ok]
        print(f"Resuming: {len(already_ok)} already-succeeded questions kept, "
              f"{len(questions)} remaining.", flush=True)

    for i, question in enumerate(questions, 1):
        print(f"[{i}/{len(questions)}] {question.id}: {question.question}", flush=True)
        entry = run_one(question)
        results = [r for r in results if r["id"] != question.id] + [entry]
        _write_results(out_path, results)
        analyze_error = entry.get("analyze", {}).get("error")
        status = "OK" if analyze_error is None else f"FAILED: {analyze_error}"
        print(f"    analyze: {status}", flush=True)
        if i < len(questions):
            time.sleep(args.sleep)

    print("\n=== SUMMARY ===")
    print(json.dumps(summarize(results), indent=2))
    print(f"\nWrote {out_path} (kept up to date after every question)")


if __name__ == "__main__":
    main()
