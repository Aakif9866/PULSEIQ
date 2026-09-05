import pytest

from app.core.config import settings


@pytest.fixture(autouse=True)
def _local_storage_root(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "LOCAL_STORAGE_ROOT", str(tmp_path))


def _signup_and_token(client, email: str) -> str:
    resp = client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "correct-horse-1"},
    )
    return resp.json()["tokens"]["access_token"]


SALES_CSV = (
    b"region,amount\n"
    b"east,10\n"
    b"east,30\n"
    b"west,5\n"
    b"west,\n"  # one null amount, to exercise null_count in profiling
)


def _upload_sales(client, headers) -> str:
    resp = client.post(
        "/api/v1/datasets",
        headers=headers,
        files={"file": ("sales.csv", SALES_CSV, "text/csv")},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def test_upload_triggers_profiling(client):
    token = _signup_and_token(client, "profiler@pulseiq.dev")
    headers = {"Authorization": f"Bearer {token}"}

    dataset_id = _upload_sales(client, headers)

    detail = client.get(f"/api/v1/datasets/{dataset_id}", headers=headers).json()
    assert detail["status"] == "profiled"
    assert detail["row_count"] == 4
    assert detail["column_count"] == 2
    columns = {c["name"]: c for c in detail["columns_profile"]}
    assert columns["region"]["null_count"] == 0
    assert columns["amount"]["null_count"] == 1


def test_group_by_sum_aggregation(client):
    token = _signup_and_token(client, "aggregator@pulseiq.dev")
    headers = {"Authorization": f"Bearer {token}"}
    dataset_id = _upload_sales(client, headers)

    resp = client.post(
        f"/api/v1/datasets/{dataset_id}/query",
        headers=headers,
        json={
            "group_by": ["region"],
            "aggregations": [{"op": "sum", "column": "amount", "alias": "total"}],
            "sort_by": "region",
        },
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["columns"] == ["region", "total"]
    assert body["rows"] == [["east", 40.0], ["west", 5.0]]
    assert body["row_count"] == 2
    assert body["truncated"] is False


def test_filter_then_raw_preview(client):
    token = _signup_and_token(client, "filterer@pulseiq.dev")
    headers = {"Authorization": f"Bearer {token}"}
    dataset_id = _upload_sales(client, headers)

    resp = client.post(
        f"/api/v1/datasets/{dataset_id}/query",
        headers=headers,
        json={"filters": [{"column": "region", "op": "eq", "value": "east"}]},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["row_count"] == 2
    assert all(row[body["columns"].index("region")] == "east" for row in body["rows"])


def test_unknown_column_rejected(client):
    token = _signup_and_token(client, "badcolumn@pulseiq.dev")
    headers = {"Authorization": f"Bearer {token}"}
    dataset_id = _upload_sales(client, headers)

    resp = client.post(
        f"/api/v1/datasets/{dataset_id}/query",
        headers=headers,
        json={"aggregations": [{"op": "sum", "column": "nonexistent"}]},
    )

    assert resp.status_code == 400


def test_row_limit_is_enforced(client, monkeypatch):
    monkeypatch.setattr(settings, "QUERY_ROW_LIMIT", 1)
    token = _signup_and_token(client, "limiter@pulseiq.dev")
    headers = {"Authorization": f"Bearer {token}"}
    dataset_id = _upload_sales(client, headers)

    resp = client.post(
        f"/api/v1/datasets/{dataset_id}/query",
        headers=headers,
        json={"sort_by": "amount"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["row_count"] == 1
    assert body["truncated"] is True


def test_query_rejected_before_profiling_succeeds(client):
    token = _signup_and_token(client, "unready@pulseiq.dev")
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.post(
        "/api/v1/datasets",
        headers=headers,
        files={"file": ("legacy.xls", b"not really xls", "application/vnd.ms-excel")},
    )
    assert resp.status_code == 201
    assert resp.json()["status"] == "profiling_failed"
    dataset_id = resp.json()["id"]

    query_resp = client.post(
        f"/api/v1/datasets/{dataset_id}/query",
        headers=headers,
        json={"aggregations": [{"op": "count"}]},
    )
    assert query_resp.status_code == 409
