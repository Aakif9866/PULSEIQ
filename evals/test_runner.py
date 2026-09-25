"""Tests for runner.py's resilience — the exact gap found live during
the Phase 8 step 3 run (docs/PROGRESS.md): killing the process partway
through lost every result still only held in memory, because results
were written once, at the very end. No real Groq calls here — run_one
is monkeypatched, matching how tests/test_analyst_engine.py mocks the
provider rather than actually calling the model.
"""
import json
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))

import runner  # noqa: E402
from eval_questions import EvalQuestion  # noqa: E402

_FAKE_QUESTIONS = [
    EvalQuestion("q1", "ecommerce", "Question one?", "get_dataset_profile", ["x"], 1, "d1"),
    EvalQuestion("q2", "ecommerce", "Question two?", "get_dataset_profile", ["x"], 2, "d2"),
    EvalQuestion("q3", "ecommerce", "Question three?", "get_dataset_profile", ["x"], 3, "d3"),
]


def _fake_entry(question_id: str, succeed: bool = True) -> dict:
    analyze = {"value_correct": True, "findings_total": 0, "findings_unverified": 0}
    if not succeed:
        analyze = {"error": "The AI provider did not return a usable response."}
    return {"id": question_id, "dataset": "ecommerce", "question": "?", "category": "x",
            "expected_value": 1, "value_description": "d", "analyze": analyze}


def test_results_are_written_after_every_question_not_only_at_the_end(tmp_path):
    out_path = tmp_path / "run.json"
    calls: list[str] = []

    def fake_run_one(question):
        calls.append(question.id)
        # By the time the THIRD question starts, the file must already
        # reflect the first two — this is the exact property that was
        # missing before the fix (a process killed right here would
        # previously have lost both of them, not just the interrupted one).
        if len(calls) == 3:
            written = json.loads(out_path.read_text())
            assert {r["id"] for r in written["results"]} == {"q1", "q2"}
        return _fake_entry(question.id)

    with (
        patch.object(runner, "QUESTIONS", _FAKE_QUESTIONS),
        patch.object(runner, "run_one", side_effect=fake_run_one),
        patch.object(sys, "argv", ["runner.py", "--sleep", "0", "--out", str(out_path)]),
    ):
        runner.main()

    assert calls == ["q1", "q2", "q3"]
    final = json.loads(out_path.read_text())
    assert {r["id"] for r in final["results"]} == {"q1", "q2", "q3"}


def test_resume_skips_already_succeeded_questions_and_keeps_their_data(tmp_path):
    out_path = tmp_path / "run.json"
    # Simulate a prior run that got q1 (succeeded) and q2 (failed) done,
    # then was interrupted before reaching q3 — exactly the real scenario.
    out_path.write_text(json.dumps({
        "summary": {},
        "results": [_fake_entry("q1", succeed=True), _fake_entry("q2", succeed=False)],
    }))

    calls: list[str] = []

    def fake_run_one(question):
        calls.append(question.id)
        return _fake_entry(question.id, succeed=True)

    with (
        patch.object(runner, "QUESTIONS", _FAKE_QUESTIONS),
        patch.object(runner, "run_one", side_effect=fake_run_one),
        patch.object(
            sys, "argv",
            ["runner.py", "--sleep", "0", "--out", str(out_path), "--resume"],
        ),
    ):
        runner.main()

    # q1 already succeeded — never re-run, spending no quota on it again.
    # q2 previously failed — re-attempted, since "resume" means "finish
    # the job", not "only fill in gaps that were never attempted".
    assert calls == ["q2", "q3"]
    final = json.loads(out_path.read_text())
    by_id = {r["id"]: r for r in final["results"]}
    assert set(by_id) == {"q1", "q2", "q3"}
    assert "error" not in by_id["q2"]["analyze"]  # re-run succeeded this time


# --- provider failures must never be scored as wrong answers -------------
# Found live on 2026-09-25: re-running while Groq's daily cap was still
# exhausted, the engine (correctly) degraded instead of crashing, and the
# runner scored those degraded replies as "succeeded" with 0% accuracy.

class _FakeUsage:
    def __init__(self, errors, daily_quota_hit=False):
        self.errors, self.daily_quota_hit = errors, daily_quota_hit
        self.total_tokens = self.call_count = self.groq_reported_ms = 0


def _run_one_with(status, errors, daily_quota_hit=False):
    from contextlib import contextmanager
    from types import SimpleNamespace

    response = SimpleNamespace(status=status, answer="Revenue averages 1.", findings=[],
                               tool_calls=[], warnings=[])

    @contextmanager
    def fake_track_usage():
        yield _FakeUsage(errors, daily_quota_hit)

    with (
        patch.object(runner, "track_usage", fake_track_usage),
        patch.object(runner, "run_analysis", return_value=response),
    ):
        return runner.run_one(_FAKE_QUESTIONS[0])


def test_degraded_answer_caused_by_provider_failure_is_an_error_not_a_score():
    entry = _run_one_with("degraded", ["RateLimitError: tokens per day"], daily_quota_hit=True)
    assert "error" in entry["analyze"]
    assert entry["analyze"]["daily_quota_hit"] is True
    summary = runner.summarize([entry])
    assert summary["analyze_succeeded"] == 0
    assert summary["analyze_value_accuracy_pct"] is None  # not 0.0


def test_a_retry_that_recovered_is_still_scored_normally():
    entry = _run_one_with("ok", ["RateLimitError: tokens per minute"])
    assert "error" not in entry["analyze"]
    assert entry["analyze"]["value_correct"] is True


def test_run_stops_at_the_daily_quota_instead_of_failing_every_remaining_question(tmp_path):
    out_path = tmp_path / "run.json"
    calls: list[str] = []

    def fake_run_one(question):
        calls.append(question.id)
        entry = _fake_entry(question.id, succeed=False)
        entry["analyze"]["daily_quota_hit"] = True
        return entry

    with (
        patch.object(runner, "QUESTIONS", _FAKE_QUESTIONS),
        patch.object(runner, "run_one", side_effect=fake_run_one),
        patch.object(sys, "argv", ["runner.py", "--sleep", "0", "--out", str(out_path)]),
    ):
        runner.main()

    assert calls == ["q1"]
