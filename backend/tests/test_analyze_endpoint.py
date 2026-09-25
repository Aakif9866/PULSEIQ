"""API-level tests for POST /datasets/{id}/analyze — the hybrid AI
Analyst endpoint. app.ai.analyst_engine.run_analysis is monkeypatched so
these exercise the HTTP/service wiring (auth, ownership, dataset-readiness
checks, request/response shape) without making a real Groq call, mirroring
how tests/test_ai_analyst.py mocks analyst_service's collaborators.
"""
from app.core.config import settings
from app.schemas.analysis import AnalyzeResponse, Finding, ToolCallRecord


def _signup_and_token(client, email: str) -> str:
    resp = client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "correct-horse-1"},
    )
    return resp.json()["tokens"]["access_token"]


SALES_CSV = b"region,amount\neast,10\neast,30\nwest,5\n"


def _upload_sales(client, headers) -> str:
    resp = client.post(
        "/api/v1/datasets",
        headers=headers,
        files={"file": ("sales.csv", SALES_CSV, "text/csv")},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def _fake_run_analysis(df, provider, question, conversation_history=None) -> AnalyzeResponse:
    return AnalyzeResponse(
        question=question,
        answer=f"There are {df.height} rows in this dataset.",
        findings=[
            Finding(
                claim="row count",
                value=df.height,
                total_rows=df.height,
                classification="unknown",
                confidence="high",
                verified=True,
            )
        ],
        tool_calls=[],
        status="ok",
    )


def test_analyze_returns_grounded_response(client, monkeypatch):
    monkeypatch.setattr(settings, "AI_PROVIDER", "groq")
    monkeypatch.setattr("app.services.deep_analysis_service.run_analysis", _fake_run_analysis)

    token = _signup_and_token(client, "analyst@pulseiq.dev")
    headers = {"Authorization": f"Bearer {token}"}
    dataset_id = _upload_sales(client, headers)

    resp = client.post(
        f"/api/v1/datasets/{dataset_id}/analyze",
        headers=headers,
        json={"question": "How many rows are there?"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "3 rows" in body["answer"]
    assert body["findings"][0]["verified"] is True


def test_analyze_surfaces_tool_error_and_degraded_status_over_http(client, monkeypatch):
    # The frontend's evidence panel (docs/PHASES.md Phase 8, step 1) reads
    # tool_calls[].result.error and status === "degraded" directly off the
    # JSON response — this proves both survive real HTTP serialization,
    # not just the in-process AnalyzeResponse object.
    def _fake_degraded_with_tool_error(df, provider, question, conversation_history=None):
        return AnalyzeResponse(
            question=question,
            answer="The AI provider did not return a usable response after retrying.",
            findings=[],
            tool_calls=[
                ToolCallRecord(
                    tool="detect_outliers",
                    arguments={"column": "does_not_exist"},
                    result={"error": "Column 'does_not_exist' not found."},
                )
            ],
            status="degraded",
        )

    monkeypatch.setattr(settings, "AI_PROVIDER", "groq")
    monkeypatch.setattr(
        "app.services.deep_analysis_service.run_analysis", _fake_degraded_with_tool_error
    )

    token = _signup_and_token(client, "analyze-toolerror@pulseiq.dev")
    headers = {"Authorization": f"Bearer {token}"}
    dataset_id = _upload_sales(client, headers)

    resp = client.post(
        f"/api/v1/datasets/{dataset_id}/analyze",
        headers=headers,
        json={"question": "Find outliers in a column that doesn't exist."},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "degraded"
    assert body["tool_calls"][0]["result"]["error"] == "Column 'does_not_exist' not found."


def test_analyze_returns_503_when_ai_disabled(client, monkeypatch):
    monkeypatch.setattr(settings, "AI_PROVIDER", "none")
    token = _signup_and_token(client, "analyze-disabled@pulseiq.dev")
    headers = {"Authorization": f"Bearer {token}"}
    dataset_id = _upload_sales(client, headers)

    resp = client.post(
        f"/api/v1/datasets/{dataset_id}/analyze",
        headers=headers,
        json={"question": "anything"},
    )
    assert resp.status_code == 503


def test_analyze_requires_auth(client):
    resp = client.post(
        "/api/v1/datasets/00000000-0000-0000-0000-000000000000/analyze",
        json={"question": "anything"},
    )
    assert resp.status_code == 401


def test_analyze_returns_404_for_another_users_dataset(client, monkeypatch):
    monkeypatch.setattr(settings, "AI_PROVIDER", "groq")
    monkeypatch.setattr("app.services.deep_analysis_service.run_analysis", _fake_run_analysis)

    owner_token = _signup_and_token(client, "analyze-owner@pulseiq.dev")
    dataset_id = _upload_sales(client, {"Authorization": f"Bearer {owner_token}"})

    intruder_token = _signup_and_token(client, "analyze-intruder@pulseiq.dev")
    resp = client.post(
        f"/api/v1/datasets/{dataset_id}/analyze",
        headers={"Authorization": f"Bearer {intruder_token}"},
        json={"question": "anything"},
    )
    assert resp.status_code == 404


def test_analyze_accepts_conversation_history(client, monkeypatch):
    monkeypatch.setattr(settings, "AI_PROVIDER", "groq")
    monkeypatch.setattr("app.services.deep_analysis_service.run_analysis", _fake_run_analysis)

    token = _signup_and_token(client, "analyze-followup@pulseiq.dev")
    headers = {"Authorization": f"Bearer {token}"}
    dataset_id = _upload_sales(client, headers)

    resp = client.post(
        f"/api/v1/datasets/{dataset_id}/analyze",
        headers=headers,
        json={
            "question": "Why?",
            "conversation_history": [
                {"question": "Which region is best?", "answer": "East, by total amount."}
            ],
        },
    )
    assert resp.status_code == 200


def test_analyze_rejects_empty_question(client, monkeypatch):
    monkeypatch.setattr(settings, "AI_PROVIDER", "groq")
    token = _signup_and_token(client, "analyze-empty@pulseiq.dev")
    headers = {"Authorization": f"Bearer {token}"}
    dataset_id = _upload_sales(client, headers)

    resp = client.post(
        f"/api/v1/datasets/{dataset_id}/analyze",
        headers=headers,
        json={"question": ""},
    )
    assert resp.status_code == 422
