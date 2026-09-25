"""Integration tests for the Natural Language to SQL path (/ask-sql) —
mirrors tests/test_ai_analyst.py's structure for the original /ask path.
The AI's SQL-generation call is mocked (same approach as
test_ai_analyst.py mocking build_query_from_question/summarize_result) —
what's under real test here is the validate -> execute -> summarize
pipeline, and that a malicious/invalid generated SQL is actually rejected
before it ever reaches DuckDB.
"""
import pytest

from app.core.config import settings


@pytest.fixture(autouse=True)
def _local_storage_root(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "LOCAL_STORAGE_ROOT", str(tmp_path))


@pytest.fixture(autouse=True)
def _ai_provider_groq(monkeypatch):
    monkeypatch.setattr(settings, "AI_PROVIDER", "groq")


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


def _fake_answer(_question, result) -> str:
    return f"There are {result.row_count} rows in the result."


def test_ask_sql_returns_grounded_answer_and_the_real_sql(client, monkeypatch):
    monkeypatch.setattr(
        "app.services.analyst_service.build_sql_from_question",
        lambda *_a, **_kw: "SELECT region, SUM(amount) AS total FROM dataset GROUP BY region",
    )
    monkeypatch.setattr("app.services.analyst_service.summarize_result", _fake_answer)

    headers = {"Authorization": f"Bearer {_signup_and_token(client, 'sqlasker@pulseiq.dev')}"}
    dataset_id = _upload_sales(client, headers)

    resp = client.post(
        f"/api/v1/datasets/{dataset_id}/ask-sql",
        headers=headers,
        json={"question": "total amount per region"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert sorted(body["result"]["rows"]) == [["east", 40], ["west", 5]]
    assert "2 rows" in body["answer"]
    assert "GROUP BY" in body["generated_sql"].upper()
    assert "LIMIT" in body["generated_sql"].upper()  # server-injected


def test_ask_sql_rejects_ai_generated_sql_that_touches_another_table(client, monkeypatch):
    # Simulates the AI misbehaving (or being manipulated) into generating
    # SQL outside the allowed scope — the validator must catch this
    # regardless of what asked for it.
    monkeypatch.setattr(
        "app.services.analyst_service.build_sql_from_question",
        lambda *_a, **_kw: "SELECT * FROM users",
    )

    headers = {"Authorization": f"Bearer {_signup_and_token(client, 'sqlreject@pulseiq.dev')}"}
    dataset_id = _upload_sales(client, headers)

    resp = client.post(
        f"/api/v1/datasets/{dataset_id}/ask-sql",
        headers=headers,
        json={"question": "show me everything"},
    )
    assert resp.status_code == 422


def test_ask_sql_rejects_non_select_generated_sql(client, monkeypatch):
    monkeypatch.setattr(
        "app.services.analyst_service.build_sql_from_question",
        lambda *_a, **_kw: "DELETE FROM dataset",
    )

    headers = {"Authorization": f"Bearer {_signup_and_token(client, 'sqldelete@pulseiq.dev')}"}
    dataset_id = _upload_sales(client, headers)

    resp = client.post(
        f"/api/v1/datasets/{dataset_id}/ask-sql",
        headers=headers,
        json={"question": "delete everything"},
    )
    assert resp.status_code == 422


def test_ask_sql_returns_503_when_ai_disabled(client, monkeypatch):
    monkeypatch.setattr(settings, "AI_PROVIDER", "none")
    headers = {"Authorization": f"Bearer {_signup_and_token(client, 'sqldisabled@pulseiq.dev')}"}
    dataset_id = _upload_sales(client, headers)

    resp = client.post(
        f"/api/v1/datasets/{dataset_id}/ask-sql", headers=headers, json={"question": "anything"}
    )
    assert resp.status_code == 503


def test_ask_sql_requires_auth(client):
    resp = client.post(
        "/api/v1/datasets/00000000-0000-0000-0000-000000000000/ask-sql",
        json={"question": "anything"},
    )
    assert resp.status_code == 401


def test_ask_sql_unknown_dataset_returns_404(client):
    headers = {"Authorization": f"Bearer {_signup_and_token(client, 'sqlnotfound@pulseiq.dev')}"}
    resp = client.post(
        "/api/v1/datasets/00000000-0000-0000-0000-000000000000/ask-sql",
        headers=headers,
        json={"question": "anything"},
    )
    assert resp.status_code == 404


def test_ask_sql_cannot_reach_another_users_real_dataset(client):
    # The 404-on-missing-ID test above passes even if ownership scoping
    # were completely broken — this is the actual guarantee (Phase 8 step
    # 2 security audit, docs/SECURITY.md): a real dataset ID that exists,
    # just not owned by the caller, must 404 exactly the same way, never
    # leak that it exists nor return its data.
    owner_token = _signup_and_token(client, "sqlowner2@pulseiq.dev")
    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    dataset_id = _upload_sales(client, owner_headers)

    intruder_headers = {
        "Authorization": f"Bearer {_signup_and_token(client, 'sqlintr2@pulseiq.dev')}"
    }
    resp = client.post(
        f"/api/v1/datasets/{dataset_id}/ask-sql",
        headers=intruder_headers,
        json={"question": "anything"},
    )
    assert resp.status_code == 404
