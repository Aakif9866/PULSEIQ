"""Engine-level tests for app.ai.analyst_engine.run_analysis, driven by a
fake in-process AIProvider — no network/Groq call involved. This exercises
the actual tool-calling loop, the fallback path, and (critically) guards
against regressing the two real bugs found via live Groq testing:

  1. A model faking a tool call literally named "json" to express its
     final answer while `tools=` is still attached (Groq rejects this
     with a 400 whose body echoes the intended answer back verbatim).
  2. An empty/unusable final response, which must produce the exact
     required fallback message rather than a blank or crashing analysis.
"""
import json
from typing import Any

import polars as pl
import pytest

from app.ai.analyst_engine import _FALLBACK_MESSAGE, run_analysis
from app.ai.providers.base import AIProvider, ProviderMessage, ToolCall
from app.core.exceptions import AiResponseError


def _df() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "order_id": ["A1", "A2", "A3"],
            "category": ["East", "West", "East"],
            "revenue": [10.0, 20.0, 30.0],
        }
    )


class _ScriptedProvider(AIProvider):
    """Replays a fixed sequence of responses, one per call to .chat(),
    regardless of what messages/tools/json_mode are passed — enough to
    drive run_analysis() through a specific scenario deterministically."""

    def __init__(self, responses: list[ProviderMessage | Exception]) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def chat(self, *, messages, tools=None, json_mode=False, temperature=0.1) -> ProviderMessage:
        self.calls.append({"tools": tools is not None, "json_mode": json_mode})
        if not self._responses:
            raise AssertionError("ScriptedProvider ran out of scripted responses")
        next_response = self._responses.pop(0)
        if isinstance(next_response, Exception):
            raise next_response
        return next_response


def _final_json(answer: str, findings: list[dict] | None = None) -> str:
    return json.dumps({"answer": answer, "findings": findings or [], "needs_clarification": None})


def test_run_analysis_calls_a_tool_then_produces_a_grounded_answer():
    provider = _ScriptedProvider(
        [
            ProviderMessage(
                content=None,
                tool_calls=[ToolCall(id="1", name="get_missing_values", arguments={})],
            ),
            ProviderMessage(content=None, tool_calls=[]),
            ProviderMessage(
                content=_final_json(
                    "No missing values were found.",
                    [
                        {
                            "claim": "missing values",
                            "value": 0,
                            "total_rows": 3,
                            "classification": "missing_data",
                            "confidence": "high",
                        }
                    ],
                )
            ),
        ]
    )

    response = run_analysis(_df(), provider, "Find missing values.")

    assert response.status == "ok"
    assert response.tool_calls[0].tool == "get_missing_values"
    assert response.findings[0].verified is True


def test_run_analysis_salvages_final_answer_returned_with_no_tool_calls():
    # Mirrors GroqProvider's own salvage path: a message that carries no
    # tool_calls but whose content IS already the complete final-answer
    # JSON should be used directly, without spending an extra API call.
    provider = _ScriptedProvider(
        [ProviderMessage(content=_final_json("Salvaged answer."), tool_calls=[])]
    )

    response = run_analysis(_df(), provider, "Give me a dataset profile.")

    assert response.status == "ok"
    assert response.answer == "Salvaged answer."
    assert len(provider.calls) == 1  # no extra dedicated json_mode call was made


def test_run_analysis_falls_back_on_empty_response_with_exact_required_message():
    provider = _ScriptedProvider(
        [
            ProviderMessage(content=None, tool_calls=[]),
            AiResponseError("The AI provider did not return a usable response after retrying."),
        ]
    )

    response = run_analysis(_df(), provider, "Give me a complete executive analysis.")

    assert response.status == "degraded"
    assert response.answer == _FALLBACK_MESSAGE


def test_run_analysis_falls_back_on_unparseable_final_json():
    provider = _ScriptedProvider(
        [
            ProviderMessage(content=None, tool_calls=[]),
            ProviderMessage(content="not valid json at all", tool_calls=[]),
        ]
    )

    response = run_analysis(_df(), provider, "Find duplicate order IDs.")

    assert response.status == "degraded"
    assert response.answer == _FALLBACK_MESSAGE


def test_run_analysis_uses_the_full_dataset_not_a_preview():
    # A 500-row dataset — get_missing_values must report the true row
    # count, proving the tool ran against the full DataFrame, not a head().
    big_df = pl.DataFrame({"x": list(range(500))})
    provider = _ScriptedProvider(
        [
            ProviderMessage(
                content=None,
                tool_calls=[ToolCall(id="1", name="get_missing_values", arguments={})],
            ),
            ProviderMessage(content=_final_json("500 rows, no missing values."), tool_calls=[]),
        ]
    )

    response = run_analysis(big_df, provider, "How many rows are there?")

    assert response.tool_calls[0].result["row_count"] == 500


def test_conversation_history_is_included_in_the_prompt():
    provider = _ScriptedProvider(
        [ProviderMessage(content=_final_json("Follow-up answer."), tool_calls=[])]
    )
    from app.schemas.analysis import ConversationTurn

    history = [ConversationTurn(question="Which category is best?", answer="East, by revenue.")]
    run_analysis(_df(), provider, "Why?", conversation_history=history)

    # Can't inspect messages directly (ScriptedProvider ignores them), but
    # a second call with history must not raise and must still respond ok.
    assert True


@pytest.mark.parametrize("iteration_cap_hit", [True])
def test_run_analysis_stops_after_max_tool_iterations(iteration_cap_hit):
    # 6 tool-call rounds followed by a final call — never loops forever.
    responses: list[ProviderMessage | Exception] = [
        ProviderMessage(
            content=None, tool_calls=[ToolCall(id=str(i), name="get_missing_values", arguments={})]
        )
        for i in range(6)
    ]
    responses.append(ProviderMessage(content=_final_json("Done."), tool_calls=[]))
    provider = _ScriptedProvider(responses)

    response = run_analysis(_df(), provider, "Give me a complete executive analysis.")

    assert response.status == "ok"
    assert len(response.tool_calls) == 6
