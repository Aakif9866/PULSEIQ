"""Saved insights end to end: save with evidence, reopen, rename, report,
link to dashboard charts, and isolation between accounts."""

import pytest

from app.core.config import settings


@pytest.fixture(autouse=True)
def _local_storage_root(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "LOCAL_STORAGE_ROOT", str(tmp_path))


def _auth(client, email):
    resp = client.post("/api/v1/auth/signup", json={"email": email, "password": "correct-horse-1"})
    return {"Authorization": f"Bearer {resp.json()['tokens']['access_token']}"}


def _dataset(client, headers) -> str:
    csv = b"region,amount\neast,10\neast,30\nwest,5\n"
    resp = client.post(
        "/api/v1/datasets", headers=headers, files={"file": ("s.csv", csv, "text/csv")}
    )
    return resp.json()["id"]


_GROUPED = {
    "tool": "group_by_aggregate",
    "arguments": {"group_by": ["region"], "column": "amount", "op": "sum"},
    "result": {"columns": ["region", "value"], "rows": [["east", 40], ["west", 5]], "row_count": 2},
}


def _save(client, headers, ds, **extra):
    body = {
        "dataset_id": ds,
        "question": "Total amount by region?",
        "answer": "East leads with 40.",
        "findings": [{"claim": "East total", "value": 40, "verified": True, "calculation": "sum"}],
        "tool_calls": [_GROUPED],
        **extra,
    }
    resp = client.post("/api/v1/insights", headers=headers, json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_save_reopen_and_rename(client):
    h = _auth(client, "life@pulseiq.dev")
    saved = _save(client, h, _dataset(client, h))
    assert saved["title"] == "Total amount by region?"  # defaults to the question
    assert saved["tool_calls"][0]["result"]["rows"][0] == ["east", 40]

    reopened = client.get(f"/api/v1/insights/{saved['id']}", headers=h).json()
    assert reopened["findings"][0]["verified"] is True and reopened["dataset_filename"] == "s.csv"

    renamed = client.patch(
        f"/api/v1/insights/{saved['id']}", headers=h, json={"title": "  East wins  "}
    )
    assert renamed.json()["title"] == "East wins"
    assert (
        client.patch(f"/api/v1/insights/{saved['id']}", headers=h, json={"title": ""}).status_code
        == 422
    )


def test_oversized_evidence_is_replaced_by_an_honest_note(client):
    h = _auth(client, "big@pulseiq.dev")
    huge = {**_GROUPED, "result": {"rows": [["x" * 50, i] for i in range(500)]}}
    saved = _save(client, h, _dataset(client, h), tool_calls=[huge])
    assert "too large to store" in saved["tool_calls"][0]["result"]["omitted"]


def test_report_is_a_downloadable_escaped_snapshot(client):
    h = _auth(client, "report@pulseiq.dev")
    ds = _dataset(client, h)
    saved = _save(client, h, ds, question="<script>alert(1)</script> by region?")
    resp = client.get(f"/api/v1/insights/{saved['id']}/report", headers=h)

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/html")
    assert "attachment" in resp.headers["content-disposition"]
    assert resp.headers["cache-control"] == "private, no-store"
    html = resp.text
    assert "<script>" not in html and "&lt;script&gt;" in html  # user text never executes
    assert "East leads with 40." in html and "1 of 1 findings verified" in html
    assert "Grouped aggregation" in html and "<svg" in html  # evidence table + chart
    assert "not proof of cause" in html  # methodology states the limits


def test_other_accounts_cannot_read_rename_or_export(client):
    owner = _auth(client, "owner-i@pulseiq.dev")
    saved = _save(client, owner, _dataset(client, owner))
    intruder = _auth(client, "intruder-i@pulseiq.dev")
    for method, path, kw in [
        ("get", f"/api/v1/insights/{saved['id']}", {}),
        ("patch", f"/api/v1/insights/{saved['id']}", {"json": {"title": "mine"}}),
        ("get", f"/api/v1/insights/{saved['id']}/report", {}),
    ]:
        assert getattr(client, method)(path, headers=intruder, **kw).status_code == 404


def test_chart_links_to_its_insight_and_survives_the_insight_being_deleted(client):
    h = _auth(client, "chartlink@pulseiq.dev")
    ds = _dataset(client, h)
    saved = _save(client, h, ds)
    dash = client.post("/api/v1/dashboards", headers=h, json={"name": "D"}).json()
    chart = client.post(
        f"/api/v1/dashboards/{dash['id']}/charts",
        headers=h,
        json={
            "dataset_id": ds,
            "title": "By region",
            "chart_type": "bar",
            "insight_id": saved["id"],
            "query": {"group_by": ["region"], "aggregations": [{"op": "sum", "column": "amount"}]},
        },
    )
    assert chart.status_code == 201 and chart.json()["insight_id"] == saved["id"]

    rename = client.patch(
        f"/api/v1/dashboards/{dash['id']}/charts/{chart.json()['id']}",
        headers=h,
        json={"title": "Renamed"},
    )
    assert rename.status_code == 204

    client.delete(f"/api/v1/insights/{saved['id']}", headers=h)
    detail = client.get(f"/api/v1/dashboards/{dash['id']}", headers=h).json()
    assert detail["charts"][0]["title"] == "Renamed"
    assert detail["charts"][0]["insight_id"] is None  # unlinked, chart kept


def test_chart_cannot_link_to_someone_elses_insight(client):
    other = _auth(client, "other-c@pulseiq.dev")
    foreign = _save(client, other, _dataset(client, other))
    h = _auth(client, "me-c@pulseiq.dev")
    ds = _dataset(client, h)
    dash = client.post("/api/v1/dashboards", headers=h, json={"name": "D"}).json()
    resp = client.post(
        f"/api/v1/dashboards/{dash['id']}/charts",
        headers=h,
        json={
            "dataset_id": ds,
            "title": "x",
            "chart_type": "bar",
            "insight_id": foreign["id"],
            "query": {"aggregations": [{"op": "count"}]},
        },
    )
    assert resp.status_code == 404


def test_report_timestamps_are_converted_to_utc_before_labelling():
    from datetime import datetime, timedelta, timezone

    from app.services.report import _utc

    ist = timezone(timedelta(hours=5, minutes=30))
    assert _utc(datetime(2026, 10, 17, 1, 49, tzinfo=ist)) == "2026-10-16 20:19 UTC"
    assert _utc(datetime(2026, 10, 16, 20, 19)) == "2026-10-16 20:19 UTC"  # naive = UTC


def test_saved_findings_are_reverified_against_the_saved_evidence(client):
    h = _auth(client, "forge@pulseiq.dev")
    saved = _save(
        client,
        h,
        _dataset(client, h),
        findings=[
            {"claim": "East total", "value": 40, "verified": True},  # in the evidence
            {"claim": "Invented", "value": 123456, "verified": True},  # not in it
        ],
    )
    assert [f["verified"] for f in saved["findings"]] == [True, False]
