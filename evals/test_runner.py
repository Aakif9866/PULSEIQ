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
