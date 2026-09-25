"""Integration tests for the SQL Explorer, query history, and saved
queries (docs/V2_ROADMAP.md's "SQL Explorer" and "Query and Insight
History" sections)."""
import pytest

from app.core.config import settings


@pytest.fixture(autouse=True)
def _local_storage_root(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "LOCAL_STORAGE_ROOT", str(tmp_path))


def _signup_and_token(client, email: str) -> str:
    resp = client.post("/api/v1/auth/signup", json={"email": email, "password": "correct-horse-1"})
    return resp.json()["tokens"]["access_token"]


SALES_CSV = b"region,amount\neast,10\neast,30\nwest,5\n"


def _upload_sales(client, headers) -> str:
    resp = client.post(
        "/api/v1/datasets", headers=headers, files={"file": ("sales.csv", SALES_CSV, "text/csv")}
    )
    assert resp.status_code == 201
    return resp.json()["id"]


# ---------------- SQL Explorer: run_sql ----------------


def test_run_sql_executes_and_returns_result(client):
    headers = {"Authorization": f"Bearer {_signup_and_token(client, 'explorer@pulseiq.dev')}"}
    dataset_id = _upload_sales(client, headers)

    resp = client.post(
        f"/api/v1/datasets/{dataset_id}/sql",
        headers=headers,
        json={
            "sql": "SELECT region, SUM(amount) AS total FROM dataset "
            "GROUP BY region ORDER BY region"
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["result"]["rows"] == [["east", 40], ["west", 5]]
    assert "LIMIT" in body["sql"].upper()


def test_run_sql_rejects_unsafe_query(client):
    headers = {"Authorization": f"Bearer {_signup_and_token(client, 'explorerbad@pulseiq.dev')}"}
    dataset_id = _upload_sales(client, headers)

    resp = client.post(
        f"/api/v1/datasets/{dataset_id}/sql", headers=headers, json={"sql": "DROP TABLE dataset"}
    )
    assert resp.status_code == 422


def test_run_sql_enforces_query_timeout(client, monkeypatch):
    # Phase 8 step 2 security audit (docs/SECURITY.md): the timeout
    # guarantee mentioned in V2_ROADMAP.md/AI_ANALYTICS.md had never
    # actually been exercised by a test, for any of the three SQL-running
    # call sites. This is the SQL Explorer's (the most directly
    # user-facing one) — a slow query must be cut off, not left to run
    # indefinitely, and must surface as a clean 408, not a raw 500/hang.
    import time

    from app.core.config import settings

    monkeypatch.setattr(settings, "QUERY_TIMEOUT_SECONDS", 1)
    monkeypatch.setattr(
        "app.services.history_service.execute_sql",
        lambda df, sql: time.sleep(3) or None,  # never actually reached in time
    )

    headers = {"Authorization": f"Bearer {_signup_and_token(client, 'explorerslow@pulseiq.dev')}"}
    dataset_id = _upload_sales(client, headers)

    resp = client.post(
        f"/api/v1/datasets/{dataset_id}/sql",
        headers=headers,
        json={"sql": "SELECT * FROM dataset"},
    )
    assert resp.status_code == 408
    assert "too long" in resp.json()["detail"].lower()


def test_run_sql_requires_auth(client):
    resp = client.post(
        "/api/v1/datasets/00000000-0000-0000-0000-000000000000/sql", json={"sql": "SELECT 1"}
    )
    assert resp.status_code == 401


def test_run_sql_unauthorized_dataset_is_404(client):
    owner_headers = {"Authorization": f"Bearer {_signup_and_token(client, 'sqlowner@pulseiq.dev')}"}
    dataset_id = _upload_sales(client, owner_headers)

    intr_token = _signup_and_token(client, "sqlintr@pulseiq.dev")
    intruder_headers = {"Authorization": f"Bearer {intr_token}"}
    resp = client.post(
        f"/api/v1/datasets/{dataset_id}/sql", headers=intruder_headers, json={"sql": "SELECT 1"}
    )
    assert resp.status_code == 404


# ---------------- Suggested queries ----------------


def test_suggested_queries_are_schema_derived(client):
    headers = {"Authorization": f"Bearer {_signup_and_token(client, 'suggest@pulseiq.dev')}"}
    dataset_id = _upload_sales(client, headers)

    resp = client.get(f"/api/v1/datasets/{dataset_id}/suggested-queries", headers=headers)
    assert resp.status_code == 200
    suggestions = resp.json()
    assert any("LIMIT 100" in s["sql"] for s in suggestions)
    assert any("region" in s["sql"] for s in suggestions)  # categorical column suggestion
    assert any("amount" in s["sql"] for s in suggestions)  # numeric column suggestion


# ---------------- Query history ----------------


def test_run_sql_is_logged_to_history(client):
    headers = {"Authorization": f"Bearer {_signup_and_token(client, 'histlog@pulseiq.dev')}"}
    dataset_id = _upload_sales(client, headers)

    client.post(
        f"/api/v1/datasets/{dataset_id}/sql", headers=headers, json={"sql": "SELECT * FROM dataset"}
    )

    history = client.get("/api/v1/history", headers=headers).json()
    assert len(history) == 1
    assert history[0]["source"] == "sql_explorer"
    assert history[0]["question"] is None
    assert history[0]["sql_text"] is not None

    filtered = client.get(f"/api/v1/history?dataset_id={dataset_id}", headers=headers).json()
    assert len(filtered) == 1


def test_history_is_owner_scoped(client):
    owner_headers = {"Authorization": f"Bearer {_signup_and_token(client, 'histown@pulseiq.dev')}"}
    dataset_id = _upload_sales(client, owner_headers)
    client.post(
        f"/api/v1/datasets/{dataset_id}/sql",
        headers=owner_headers,
        json={"sql": "SELECT * FROM dataset"},
    )

    intr_token = _signup_and_token(client, "histintr@pulseiq.dev")
    intruder_headers = {"Authorization": f"Bearer {intr_token}"}
    assert client.get("/api/v1/history", headers=intruder_headers).json() == []


def test_history_requires_auth(client):
    assert client.get("/api/v1/history").status_code == 401


# ---------------- Saved queries ----------------


def test_saved_query_crud(client):
    headers = {"Authorization": f"Bearer {_signup_and_token(client, 'saveq@pulseiq.dev')}"}
    dataset_id = _upload_sales(client, headers)

    create_resp = client.post(
        "/api/v1/queries",
        headers=headers,
        json={
            "dataset_id": dataset_id,
            "name": "Region totals",
            "sql_text": "SELECT * FROM dataset",
        },
    )
    assert create_resp.status_code == 201
    query_id = create_resp.json()["id"]

    list_resp = client.get("/api/v1/queries", headers=headers)
    assert len(list_resp.json()) == 1

    filtered = client.get(f"/api/v1/queries?dataset_id={dataset_id}", headers=headers)
    assert len(filtered.json()) == 1

    delete_resp = client.delete(f"/api/v1/queries/{query_id}", headers=headers)
    assert delete_resp.status_code == 204
    assert client.get("/api/v1/queries", headers=headers).json() == []


def test_saved_query_rejects_unauthorized_dataset(client):
    owner_headers = {"Authorization": f"Bearer {_signup_and_token(client, 'sqowner@pulseiq.dev')}"}
    dataset_id = _upload_sales(client, owner_headers)

    intr_token = _signup_and_token(client, "sqintr@pulseiq.dev")
    intruder_headers = {"Authorization": f"Bearer {intr_token}"}
    resp = client.post(
        "/api/v1/queries",
        headers=intruder_headers,
        json={"dataset_id": dataset_id, "name": "x", "sql_text": "SELECT 1"},
    )
    assert resp.status_code == 404


def test_cannot_delete_another_users_saved_query(client):
    owner_headers = {"Authorization": f"Bearer {_signup_and_token(client, 'delowner@pulseiq.dev')}"}
    dataset_id = _upload_sales(client, owner_headers)
    query_id = client.post(
        "/api/v1/queries",
        headers=owner_headers,
        json={"dataset_id": dataset_id, "name": "mine", "sql_text": "SELECT 1"},
    ).json()["id"]

    intr_token = _signup_and_token(client, "delintr@pulseiq.dev")
    intruder_headers = {"Authorization": f"Bearer {intr_token}"}
    resp = client.delete(f"/api/v1/queries/{query_id}", headers=intruder_headers)
    assert resp.status_code == 404


# ---------------- AI paths log to history too ----------------


def test_ask_logs_to_history(client, monkeypatch):
    from app.schemas.dataset_query import Aggregation, DatasetQueryRequest

    monkeypatch.setattr(settings, "AI_PROVIDER", "groq")
    fake_agg = Aggregation(op="sum", column="amount", alias="total")
    monkeypatch.setattr(
        "app.services.analyst_service.build_query_from_question",
        lambda *_a, **_kw: DatasetQueryRequest(group_by=["region"], aggregations=[fake_agg]),
    )
    monkeypatch.setattr("app.services.analyst_service.summarize_result", lambda *_a, **_kw: "ok")

    headers = {"Authorization": f"Bearer {_signup_and_token(client, 'asklog@pulseiq.dev')}"}
    dataset_id = _upload_sales(client, headers)

    client.post(
        f"/api/v1/datasets/{dataset_id}/ask",
        headers=headers,
        json={"question": "totals per region"},
    )

    history = client.get("/api/v1/history", headers=headers).json()
    assert len(history) == 1
    assert history[0]["source"] == "ai_structured"
    assert history[0]["question"] == "totals per region"
    assert history[0]["sql_text"] is None


def test_ask_sql_logs_to_history(client, monkeypatch):
    monkeypatch.setattr(settings, "AI_PROVIDER", "groq")
    monkeypatch.setattr(
        "app.services.analyst_service.build_sql_from_question",
        lambda *_a, **_kw: "SELECT region, SUM(amount) AS total FROM dataset GROUP BY region",
    )
    monkeypatch.setattr("app.services.analyst_service.summarize_result", lambda *_a, **_kw: "ok")

    headers = {"Authorization": f"Bearer {_signup_and_token(client, 'asksqllog@pulseiq.dev')}"}
    dataset_id = _upload_sales(client, headers)

    client.post(
        f"/api/v1/datasets/{dataset_id}/ask-sql",
        headers=headers,
        json={"question": "totals per region"},
    )

    history = client.get("/api/v1/history", headers=headers).json()
    assert len(history) == 1
    assert history[0]["source"] == "ai_sql"
    assert history[0]["sql_text"] is not None


def test_analyze_logs_to_history_and_history_lists_it(client, monkeypatch):
    # Regression test: DeepAnalysisService logs with source="ai_deep_analysis",
    # which used to be missing from QueryHistoryRead's QuerySource Literal —
    # GET /history 500'd the moment anyone had ever used the AI Analyst.
    from app.schemas.analysis import AnalyzeResponse

    monkeypatch.setattr(settings, "AI_PROVIDER", "groq")
    monkeypatch.setattr(
        "app.services.deep_analysis_service.run_analysis",
        lambda df, provider, question, conversation_history=None: AnalyzeResponse(
            question=question, answer="ok", status="ok"
        ),
    )

    headers = {"Authorization": f"Bearer {_signup_and_token(client, 'analyzelog@pulseiq.dev')}"}
    dataset_id = _upload_sales(client, headers)

    resp = client.post(
        f"/api/v1/datasets/{dataset_id}/analyze",
        headers=headers,
        json={"question": "Give me a complete executive analysis."},
    )
    assert resp.status_code == 200

    history = client.get("/api/v1/history", headers=headers)
    assert history.status_code == 200
    body = history.json()
    assert len(body) == 1
    assert body[0]["source"] == "ai_deep_analysis"
    assert body[0]["question"] == "Give me a complete executive analysis."
