"""Dataset versioning: refresh a dataset without losing history, detect
schema changes, keep saved insights honest, and re-run anomaly checks on
the new data."""

from pathlib import Path

import pytest

from app.ai.answer_cache import cache_key
from app.core.config import settings

V1 = b"date,region,revenue\n2024-01-01,N,100\n2024-01-02,S,110\n2024-01-03,N,105\n2024-01-04,S,95\n"
# v2: a new column, a removed column, and a huge final day (an anomaly).
V2 = (
    b"date,revenue,channel\n2024-01-01,100,web\n2024-01-02,110,web\n2024-01-03,105,store\n"
    b"2024-01-04,95,web\n2024-01-05,900,store\n"
)


@pytest.fixture(autouse=True)
def _local_storage_root(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "LOCAL_STORAGE_ROOT", str(tmp_path))
    return tmp_path


def _auth(client, email):
    resp = client.post("/api/v1/auth/signup", json={"email": email, "password": "correct-horse-1"})
    return {"Authorization": f"Bearer {resp.json()['tokens']['access_token']}"}


def _upload(client, h, content=V1):
    resp = client.post(
        "/api/v1/datasets", headers=h, files={"file": ("s.csv", content, "text/csv")}
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def _new_version(client, h, ds, content=V2, name="s2.csv"):
    return client.post(
        f"/api/v1/datasets/{ds}/versions", headers=h, files={"file": (name, content, "text/csv")}
    )


def test_new_version_keeps_history_and_reports_schema_changes(client):
    h = _auth(client, "ver@pulseiq.dev")
    ds = _upload(client, h)
    assert [
        v["version"] for v in client.get(f"/api/v1/datasets/{ds}/versions", headers=h).json()
    ] == [1]

    resp = _new_version(client, h, ds)
    assert resp.status_code == 201
    body = resp.json()
    assert body["dataset"]["version"] == 2 and body["dataset"]["row_count"] == 5
    changes = body["version"]["schema_changes"]
    assert changes["previous_version"] == 1
    assert changes["added"] == ["channel"] and changes["removed"] == ["region"]
    assert changes["row_count_change"] == 1

    history = client.get(f"/api/v1/datasets/{ds}/versions", headers=h).json()
    assert [(v["version"], v["original_filename"]) for v in history] == [
        (2, "s2.csv"),
        (1, "s.csv"),
    ]
    assert history[1]["schema_changes"] is None and history[1]["file_kept"] is True


def test_queries_and_briefing_use_the_new_version(client):
    h = _auth(client, "ver-query@pulseiq.dev")
    ds = _upload(client, h)
    _new_version(client, h, ds)
    result = client.post(
        f"/api/v1/datasets/{ds}/query",
        headers=h,
        json={"aggregations": [{"op": "sum", "column": "revenue", "alias": "t"}]},
    ).json()
    assert result["rows"][0][0] == 1310  # v2 total, not v1's 410


def test_insight_from_an_older_version_is_marked_as_such(client):
    h = _auth(client, "ver-insight@pulseiq.dev")
    ds = _upload(client, h)
    saved = client.post(
        "/api/v1/insights",
        headers=h,
        json={"dataset_id": ds, "question": "Total?", "answer": "410."},
    ).json()
    assert (saved["dataset_version"], saved["current_dataset_version"]) == (1, 1)

    _new_version(client, h, ds)
    reopened = client.get(f"/api/v1/insights/{saved['id']}", headers=h).json()
    assert (reopened["dataset_version"], reopened["current_dataset_version"]) == (1, 2)
    report = client.get(f"/api/v1/insights/{saved['id']}/report", headers=h).text
    assert "Computed on version 1; the dataset is now at version 2" in report


def test_ai_answers_are_cached_per_version():
    import uuid

    ds = uuid.uuid4()
    assert cache_key(ds, "total?", 1) != cache_key(ds, "total?", 2)
    assert cache_key(ds, "Total? ", 1) == cache_key(ds, "total?", 1)


def test_anomaly_checks_rerun_on_a_new_version_without_duplicates(client):
    h = _auth(client, "ver-check@pulseiq.dev")
    ds = _upload(client, h)
    created = client.post(
        "/api/v1/monitors",
        headers=h,
        json={
            "dataset_id": ds,
            "name": "Revenue",
            "metric_column": "revenue",
            "aggregation": "sum",
            "time_column": "date",
            "baseline_strategy": "previous_period",
            "threshold_percent": 50.0,
            "check_frequency": "manual",
            "notify_email": False,
        },
    )
    assert created.status_code == 201, created.text

    first = _new_version(client, h, ds).json()
    assert first["checks_run"] == 1 and first["new_anomalies"] == 1  # 95 -> 900

    again = _new_version(client, h, ds, name="s3.csv").json()  # same data again
    assert again["checks_run"] == 1 and again["new_anomalies"] == 0  # already reported


def test_old_files_are_pruned_but_history_kept_and_delete_removes_everything(
    client, monkeypatch, _local_storage_root
):
    monkeypatch.setattr(settings, "MAX_DATASET_VERSIONS_KEPT", 2)
    h = _auth(client, "ver-prune@pulseiq.dev")
    ds = _upload(client, h)
    _new_version(client, h, ds)
    _new_version(client, h, ds, name="s3.csv")
    history = client.get(f"/api/v1/datasets/{ds}/versions", headers=h).json()
    assert [v["file_kept"] for v in history] == [True, True, False]  # v1's file pruned
    assert len(list(Path(_local_storage_root).rglob("*.csv"))) == 2

    assert client.delete(f"/api/v1/datasets/{ds}", headers=h).status_code == 204
    assert list(Path(_local_storage_root).rglob("*.csv")) == []


def test_only_the_owner_can_version_a_dataset(client):
    owner = _auth(client, "ver-owner@pulseiq.dev")
    ds = _upload(client, owner)
    intruder = _auth(client, "ver-intruder@pulseiq.dev")
    assert _new_version(client, intruder, ds).status_code == 404
    assert client.get(f"/api/v1/datasets/{ds}/versions", headers=intruder).status_code == 404


def test_the_shared_demo_dataset_cannot_be_replaced(client, monkeypatch):
    from app.demo import DEMO_FILENAME

    monkeypatch.setattr(settings, "DEMO_USER_EMAIL", "demo-v@pulseiq.dev")
    h = _auth(client, "demo-v@pulseiq.dev")
    resp = client.post(
        "/api/v1/datasets", headers=h, files={"file": (DEMO_FILENAME, V1, "text/csv")}
    )
    demo_ds = resp.json()["id"]
    assert _new_version(client, h, demo_ds).status_code == 403
    own = _upload(client, h)  # the demo account's other datasets still version fine
    assert _new_version(client, h, own).status_code == 201
