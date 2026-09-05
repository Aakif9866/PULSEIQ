import pytest

from app.core.config import settings
from app.schemas.dataset_query import Aggregation, DatasetQueryRequest


@pytest.fixture(autouse=True)
def _local_storage_root(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "LOCAL_STORAGE_ROOT", str(tmp_path))


@pytest.fixture(autouse=True)
def _ai_provider_groq(monkeypatch):
    monkeypatch.setattr(settings, "AI_PROVIDER", "groq")


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


def _fake_query(*_args, **_kwargs) -> DatasetQueryRequest:
    return DatasetQueryRequest(
        group_by=["region"],
        aggregations=[Aggregation(op="sum", column="amount", alias="total")],
        sort_by="region",
    )


def _fake_answer(_question, result) -> str:
    return f"There are {result.row_count} regions in the result."


def test_ask_returns_grounded_answer(client, monkeypatch):
    monkeypatch.setattr("app.services.analyst_service.build_query_from_question", _fake_query)
    monkeypatch.setattr("app.services.analyst_service.summarize_result", _fake_answer)

    token = _signup_and_token(client, "asker@pulseiq.dev")
    headers = {"Authorization": f"Bearer {token}"}
    dataset_id = _upload_sales(client, headers)

    resp = client.post(
        f"/api/v1/datasets/{dataset_id}/ask",
        headers=headers,
        json={"question": "What's the total amount per region?"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["result"]["rows"] == [["east", 40.0], ["west", 5.0]]
    assert "2 regions" in body["answer"]
    assert body["query"]["group_by"] == ["region"]


def test_ask_returns_503_when_ai_disabled(client, monkeypatch):
    monkeypatch.setattr(settings, "AI_PROVIDER", "none")
    token = _signup_and_token(client, "disabled@pulseiq.dev")
    headers = {"Authorization": f"Bearer {token}"}
    dataset_id = _upload_sales(client, headers)

    resp = client.post(
        f"/api/v1/datasets/{dataset_id}/ask",
        headers=headers,
        json={"question": "anything"},
    )
    assert resp.status_code == 503


def test_ask_requires_auth(client):
    resp = client.post(
        "/api/v1/datasets/00000000-0000-0000-0000-000000000000/ask",
        json={"question": "anything"},
    )
    assert resp.status_code == 401


def test_save_and_list_insight(client, monkeypatch):
    monkeypatch.setattr("app.services.analyst_service.build_query_from_question", _fake_query)
    monkeypatch.setattr("app.services.analyst_service.summarize_result", _fake_answer)

    token = _signup_and_token(client, "saver@pulseiq.dev")
    headers = {"Authorization": f"Bearer {token}"}
    dataset_id = _upload_sales(client, headers)

    ask_resp = client.post(
        f"/api/v1/datasets/{dataset_id}/ask",
        headers=headers,
        json={"question": "Total amount per region?"},
    )
    ask_body = ask_resp.json()

    save_resp = client.post(
        "/api/v1/insights",
        headers=headers,
        json={
            "dataset_id": dataset_id,
            "question": ask_body["question"],
            "answer": ask_body["answer"],
            "query": ask_body["query"],
            "row_count": ask_body["result"]["row_count"],
        },
    )
    assert save_resp.status_code == 201
    saved = save_resp.json()
    assert saved["dataset_filename"] == "sales.csv"
    assert saved["question"] == "Total amount per region?"

    list_resp = client.get("/api/v1/insights", headers=headers)
    assert list_resp.status_code == 200
    assert any(i["id"] == saved["id"] for i in list_resp.json())


def test_cannot_save_insight_for_another_users_dataset(client, monkeypatch):
    monkeypatch.setattr("app.services.analyst_service.build_query_from_question", _fake_query)
    monkeypatch.setattr("app.services.analyst_service.summarize_result", _fake_answer)

    owner_token = _signup_and_token(client, "insight-owner@pulseiq.dev")
    dataset_id = _upload_sales(client, {"Authorization": f"Bearer {owner_token}"})

    intruder_token = _signup_and_token(client, "insight-intruder@pulseiq.dev")
    resp = client.post(
        "/api/v1/insights",
        headers={"Authorization": f"Bearer {intruder_token}"},
        json={
            "dataset_id": dataset_id,
            "question": "q",
            "answer": "a",
            "query": {"aggregations": [{"op": "count"}]},
            "row_count": 1,
        },
    )
    assert resp.status_code == 404


def test_delete_insight(client, monkeypatch):
    monkeypatch.setattr("app.services.analyst_service.build_query_from_question", _fake_query)
    monkeypatch.setattr("app.services.analyst_service.summarize_result", _fake_answer)

    token = _signup_and_token(client, "deleter@pulseiq.dev")
    headers = {"Authorization": f"Bearer {token}"}
    dataset_id = _upload_sales(client, headers)

    ask_body = client.post(
        f"/api/v1/datasets/{dataset_id}/ask", headers=headers, json={"question": "q"}
    ).json()
    saved = client.post(
        "/api/v1/insights",
        headers=headers,
        json={
            "dataset_id": dataset_id,
            "question": ask_body["question"],
            "answer": ask_body["answer"],
            "query": ask_body["query"],
            "row_count": ask_body["result"]["row_count"],
        },
    ).json()

    delete_resp = client.delete(f"/api/v1/insights/{saved['id']}", headers=headers)
    assert delete_resp.status_code == 204

    list_resp = client.get("/api/v1/insights", headers=headers)
    assert all(i["id"] != saved["id"] for i in list_resp.json())
