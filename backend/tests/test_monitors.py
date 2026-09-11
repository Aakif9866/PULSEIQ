"""Integration tests for the anomaly monitoring API: authorization,
end-to-end detection through the real HTTP layer, alerting (including
failure isolation), and AI-explanation failure isolation. The deterministic
detection engine itself is covered in isolation in
tests/test_anomaly_detection.py — this file exercises it through the full
Monitor -> Detect -> Explain -> Alert pipeline.
"""
import pytest

from app.core.config import settings
from app.core.exceptions import AiResponseError
from app.services.monitor_service import MonitorService
from app.storage import get_storage_provider


@pytest.fixture(autouse=True)
def _local_storage_root(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "LOCAL_STORAGE_ROOT", str(tmp_path))


def _signup_and_token(client, email: str) -> str:
    resp = client.post("/api/v1/auth/signup", json={"email": email, "password": "correct-horse-1"})
    assert resp.status_code == 201
    return resp.json()["tokens"]["access_token"]


NORMAL_CSV = b"date,revenue\n2026-01-01,100\n2026-01-02,102\n"
ANOMALY_CSV = b"date,revenue\n2026-01-01,100\n2026-01-02,200\n"
ONE_PERIOD_CSV = b"date,revenue\n2026-01-01,100\n"


def _upload(client, headers, content: bytes = NORMAL_CSV, filename: str = "sales.csv") -> str:
    resp = client.post(
        "/api/v1/datasets", headers=headers, files={"file": (filename, content, "text/csv")}
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def _monitor_payload(dataset_id: str, **overrides: object) -> dict:
    payload = {
        "dataset_id": dataset_id,
        "name": "Revenue watch",
        "metric_column": "revenue",
        "aggregation": "sum",
        "time_column": "date",
        "baseline_strategy": "previous_period",
        "threshold_percent": 20.0,
        "check_frequency": "manual",
        "notify_email": False,
    }
    payload.update(overrides)
    return payload


# ---------------- auth ----------------


def test_monitors_require_auth(client):
    assert client.get("/api/v1/monitors").status_code == 401


# ---------------- authorization ----------------


def test_cannot_create_monitor_for_another_users_dataset(client):
    owner_token = _signup_and_token(client, "monitor-owner@pulseiq.dev")
    dataset_id = _upload(client, {"Authorization": f"Bearer {owner_token}"})

    intruder_token = _signup_and_token(client, "monitor-intruder@pulseiq.dev")
    resp = client.post(
        "/api/v1/monitors",
        headers={"Authorization": f"Bearer {intruder_token}"},
        json=_monitor_payload(dataset_id),
    )
    assert resp.status_code == 404


def test_cannot_access_another_users_monitor(client):
    owner_headers = {"Authorization": f"Bearer {_signup_and_token(client, 'mo2@pulseiq.dev')}"}
    dataset_id = _upload(client, owner_headers)
    monitor_id = client.post(
        "/api/v1/monitors", headers=owner_headers, json=_monitor_payload(dataset_id)
    ).json()["id"]

    intruder_headers = {"Authorization": f"Bearer {_signup_and_token(client, 'mi2@pulseiq.dev')}"}

    assert client.get(f"/api/v1/monitors/{monitor_id}", headers=intruder_headers).status_code == 404
    assert (
        client.patch(
            f"/api/v1/monitors/{monitor_id}", headers=intruder_headers, json={"name": "x"}
        ).status_code
        == 404
    )
    run_resp = client.post(f"/api/v1/monitors/{monitor_id}/run", headers=intruder_headers)
    assert run_resp.status_code == 404
    delete_resp = client.delete(f"/api/v1/monitors/{monitor_id}", headers=intruder_headers)
    assert delete_resp.status_code == 404


def test_cannot_reach_another_users_anomalies(client):
    owner_headers = {"Authorization": f"Bearer {_signup_and_token(client, 'mo3@pulseiq.dev')}"}
    dataset_id = _upload(client, owner_headers, content=ANOMALY_CSV)
    monitor_id = client.post(
        "/api/v1/monitors", headers=owner_headers, json=_monitor_payload(dataset_id)
    ).json()["id"]
    client.post(f"/api/v1/monitors/{monitor_id}/run", headers=owner_headers)

    intruder_headers = {"Authorization": f"Bearer {_signup_and_token(client, 'mi3@pulseiq.dev')}"}

    filtered = client.get(
        f"/api/v1/monitors/anomalies?monitor_id={monitor_id}", headers=intruder_headers
    )
    assert filtered.status_code == 404

    own_list = client.get("/api/v1/monitors/anomalies", headers=intruder_headers)
    assert own_list.status_code == 200
    assert own_list.json() == []


def test_create_monitor_rejects_unknown_column(client):
    headers = {"Authorization": f"Bearer {_signup_and_token(client, 'badcol@pulseiq.dev')}"}
    dataset_id = _upload(client, headers)
    resp = client.post(
        "/api/v1/monitors",
        headers=headers,
        json=_monitor_payload(dataset_id, metric_column="does_not_exist"),
    )
    assert resp.status_code == 422


def test_create_monitor_rejects_dataset_that_failed_profiling(client):
    headers = {"Authorization": f"Bearer {_signup_and_token(client, 'notready@pulseiq.dev')}"}
    upload_resp = client.post(
        "/api/v1/datasets",
        headers=headers,
        files={"file": ("legacy.xls", b"not a real xls", "application/vnd.ms-excel")},
    )
    assert upload_resp.status_code == 201
    dataset_id = upload_resp.json()["id"]

    resp = client.post("/api/v1/monitors", headers=headers, json=_monitor_payload(dataset_id))
    assert resp.status_code == 409


# ---------------- CRUD ----------------


def test_monitor_crud(client):
    headers = {"Authorization": f"Bearer {_signup_and_token(client, 'crud@pulseiq.dev')}"}
    dataset_id = _upload(client, headers)

    create_resp = client.post(
        "/api/v1/monitors", headers=headers, json=_monitor_payload(dataset_id)
    )
    assert create_resp.status_code == 201
    monitor = create_resp.json()
    assert monitor["name"] == "Revenue watch"
    assert monitor["is_enabled"] is True
    assert monitor["dataset_filename"] == "sales.csv"
    assert monitor["last_checked_at"] is None

    assert len(client.get("/api/v1/monitors", headers=headers).json()) == 1

    update_resp = client.patch(
        f"/api/v1/monitors/{monitor['id']}",
        headers=headers,
        json={"is_enabled": False, "threshold_percent": 30.0},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["is_enabled"] is False
    assert update_resp.json()["threshold_percent"] == 30.0

    delete_resp = client.delete(f"/api/v1/monitors/{monitor['id']}", headers=headers)
    assert delete_resp.status_code == 204
    assert client.get(f"/api/v1/monitors/{monitor['id']}", headers=headers).status_code == 404


# ---------------- detection through the full pipeline ----------------


def test_run_monitor_normal_metric_is_no_anomaly_and_creates_no_record(client):
    headers = {"Authorization": f"Bearer {_signup_and_token(client, 'normal@pulseiq.dev')}"}
    dataset_id = _upload(client, headers, content=NORMAL_CSV)
    monitor_id = client.post(
        "/api/v1/monitors", headers=headers, json=_monitor_payload(dataset_id)
    ).json()["id"]

    run_resp = client.post(f"/api/v1/monitors/{monitor_id}/run", headers=headers)
    assert run_resp.status_code == 200
    body = run_resp.json()
    assert body["status"] == "NO_ANOMALY"
    assert body["anomaly"] is None

    assert client.get("/api/v1/monitors/anomalies", headers=headers).json() == []

    monitor = client.get(f"/api/v1/monitors/{monitor_id}", headers=headers).json()
    assert monitor["last_status"] == "NO_ANOMALY"
    assert monitor["last_checked_at"] is not None


def test_run_monitor_with_one_period_is_insufficient_data(client):
    headers = {"Authorization": f"Bearer {_signup_and_token(client, 'insuff@pulseiq.dev')}"}
    dataset_id = _upload(client, headers, content=ONE_PERIOD_CSV)
    monitor_id = client.post(
        "/api/v1/monitors", headers=headers, json=_monitor_payload(dataset_id)
    ).json()["id"]

    result = client.post(f"/api/v1/monitors/{monitor_id}/run", headers=headers).json()
    assert result["status"] == "INSUFFICIENT_DATA"
    assert result["anomaly"] is None


def test_run_monitor_detects_anomaly_and_persists_it(client):
    headers = {"Authorization": f"Bearer {_signup_and_token(client, 'anomaly@pulseiq.dev')}"}
    dataset_id = _upload(client, headers, content=ANOMALY_CSV)
    monitor_id = client.post(
        "/api/v1/monitors", headers=headers, json=_monitor_payload(dataset_id)
    ).json()["id"]

    run_resp = client.post(f"/api/v1/monitors/{monitor_id}/run", headers=headers)
    assert run_resp.status_code == 200
    body = run_resp.json()
    assert body["status"] == "ANOMALY_DETECTED"
    assert body["anomaly"]["direction"] == "increase"
    assert body["anomaly"]["severity"] in {"low", "medium", "high"}
    assert body["anomaly"]["detection_method"] == "percentage_change"

    all_anomalies = client.get("/api/v1/monitors/anomalies", headers=headers).json()
    assert len(all_anomalies) == 1
    assert all_anomalies[0]["metric_column"] == "revenue"
    assert all_anomalies[0]["monitor_name"] == "Revenue watch"

    filtered = client.get(
        f"/api/v1/monitors/anomalies?monitor_id={monitor_id}", headers=headers
    ).json()
    assert len(filtered) == 1


def test_running_monitor_twice_does_not_duplicate_anomaly_or_alert(client, monkeypatch):
    sent_emails: list[dict] = []
    monkeypatch.setattr(
        "app.services.monitor_service.send_email", lambda **kwargs: sent_emails.append(kwargs)
    )

    headers = {"Authorization": f"Bearer {_signup_and_token(client, 'dup@pulseiq.dev')}"}
    dataset_id = _upload(client, headers, content=ANOMALY_CSV)
    monitor_id = client.post(
        "/api/v1/monitors", headers=headers, json=_monitor_payload(dataset_id, notify_email=True)
    ).json()["id"]

    first = client.post(f"/api/v1/monitors/{monitor_id}/run", headers=headers).json()
    second = client.post(f"/api/v1/monitors/{monitor_id}/run", headers=headers).json()

    assert first["anomaly"]["id"] == second["anomaly"]["id"]
    assert len(sent_emails) == 1  # not re-sent on the second, duplicate run

    anomalies = client.get(
        f"/api/v1/monitors/anomalies?monitor_id={monitor_id}", headers=headers
    ).json()
    assert len(anomalies) == 1


# ---------------- alerting ----------------


def test_anomaly_generates_email_alert_when_enabled(client, monkeypatch):
    sent: list[dict] = []
    monkeypatch.setattr("app.services.monitor_service.send_email", lambda **kw: sent.append(kw))

    email = "alert-ok@pulseiq.dev"
    headers = {"Authorization": f"Bearer {_signup_and_token(client, email)}"}
    dataset_id = _upload(client, headers, content=ANOMALY_CSV)
    monitor_id = client.post(
        "/api/v1/monitors", headers=headers, json=_monitor_payload(dataset_id, notify_email=True)
    ).json()["id"]

    result = client.post(f"/api/v1/monitors/{monitor_id}/run", headers=headers).json()
    assert result["anomaly"]["alert_sent"] is True
    assert result["anomaly"]["alert_error"] is None
    assert result["anomaly"]["alert_sent_at"] is not None
    assert len(sent) == 1
    assert sent[0]["to"] == email


def test_normal_metric_does_not_trigger_email(client, monkeypatch):
    sent: list[dict] = []
    monkeypatch.setattr("app.services.monitor_service.send_email", lambda **kw: sent.append(kw))

    headers = {"Authorization": f"Bearer {_signup_and_token(client, 'alert-none@pulseiq.dev')}"}
    dataset_id = _upload(client, headers, content=NORMAL_CSV)
    monitor_id = client.post(
        "/api/v1/monitors", headers=headers, json=_monitor_payload(dataset_id, notify_email=True)
    ).json()["id"]

    client.post(f"/api/v1/monitors/{monitor_id}/run", headers=headers)
    assert sent == []


def test_email_failure_does_not_corrupt_anomaly_record(client, monkeypatch):
    def _boom(**_kwargs):
        raise RuntimeError("smtp exploded")

    monkeypatch.setattr("app.services.monitor_service.send_email", _boom)

    headers = {"Authorization": f"Bearer {_signup_and_token(client, 'alert-fail@pulseiq.dev')}"}
    dataset_id = _upload(client, headers, content=ANOMALY_CSV)
    monitor_id = client.post(
        "/api/v1/monitors", headers=headers, json=_monitor_payload(dataset_id, notify_email=True)
    ).json()["id"]

    resp = client.post(f"/api/v1/monitors/{monitor_id}/run", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ANOMALY_DETECTED"
    assert body["anomaly"] is not None
    assert body["anomaly"]["alert_sent"] is False
    assert "smtp exploded" in body["anomaly"]["alert_error"]

    # Confirmed persisted, not rolled back, by re-fetching independently.
    anomalies = client.get(
        f"/api/v1/monitors/anomalies?monitor_id={monitor_id}", headers=headers
    ).json()
    assert len(anomalies) == 1
    assert anomalies[0]["alert_sent"] is False


# ---------------- AI explanation ----------------


def test_ai_explanation_reaches_ai_layer_with_structured_context(client, monkeypatch):
    monkeypatch.setattr(settings, "AI_PROVIDER", "groq")
    captured: dict[str, object] = {}

    def _fake_explain(context: dict[str, object]) -> str:
        captured.update(context)
        return "Revenue moved because of a plausible business reason."

    monkeypatch.setattr("app.ai.anomaly_explainer.explain_anomaly", _fake_explain)

    headers = {"Authorization": f"Bearer {_signup_and_token(client, 'ai-ok@pulseiq.dev')}"}
    dataset_id = _upload(client, headers, content=ANOMALY_CSV)
    monitor_id = client.post(
        "/api/v1/monitors", headers=headers, json=_monitor_payload(dataset_id)
    ).json()["id"]

    result = client.post(f"/api/v1/monitors/{monitor_id}/run", headers=headers).json()
    expected_explanation = "Revenue moved because of a plausible business reason."
    assert result["anomaly"]["explanation"] == expected_explanation
    assert captured["metric"] == "revenue"
    assert captured["direction"] == "increase"
    assert "observed_value" in captured
    assert "baseline_value" in captured


def test_ai_explanation_failure_does_not_block_detection(client, monkeypatch):
    monkeypatch.setattr(settings, "AI_PROVIDER", "groq")

    def _boom(_context: dict[str, object]) -> str:
        raise AiResponseError("groq is down")

    monkeypatch.setattr("app.ai.anomaly_explainer.explain_anomaly", _boom)

    headers = {"Authorization": f"Bearer {_signup_and_token(client, 'ai-fail@pulseiq.dev')}"}
    dataset_id = _upload(client, headers, content=ANOMALY_CSV)
    monitor_id = client.post(
        "/api/v1/monitors", headers=headers, json=_monitor_payload(dataset_id)
    ).json()["id"]

    resp = client.post(f"/api/v1/monitors/{monitor_id}/run", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ANOMALY_DETECTED"
    assert body["anomaly"]["explanation"] is None


def test_no_ai_explanation_attempted_when_ai_provider_disabled(client, monkeypatch):
    monkeypatch.setattr(settings, "AI_PROVIDER", "none")
    called: list[dict] = []
    monkeypatch.setattr(
        "app.ai.anomaly_explainer.explain_anomaly",
        lambda context: called.append(context) or "should never be used",
    )

    headers = {"Authorization": f"Bearer {_signup_and_token(client, 'ai-off@pulseiq.dev')}"}
    dataset_id = _upload(client, headers, content=ANOMALY_CSV)
    monitor_id = client.post(
        "/api/v1/monitors", headers=headers, json=_monitor_payload(dataset_id)
    ).json()["id"]

    result = client.post(f"/api/v1/monitors/{monitor_id}/run", headers=headers).json()
    assert result["anomaly"]["explanation"] is None
    assert called == []


# ---------------- scheduler (not HTTP-reachable; exercised directly) ----------------


def test_run_due_monitors_skips_manual_frequency(client, db_session):
    headers = {"Authorization": f"Bearer {_signup_and_token(client, 'sched@pulseiq.dev')}"}
    dataset_id = _upload(client, headers, content=ANOMALY_CSV)

    manual_id = client.post(
        "/api/v1/monitors",
        headers=headers,
        json=_monitor_payload(dataset_id, check_frequency="manual"),
    ).json()["id"]
    daily_id = client.post(
        "/api/v1/monitors",
        headers=headers,
        json=_monitor_payload(dataset_id, name="Daily watch", check_frequency="daily"),
    ).json()["id"]

    service = MonitorService(db_session, get_storage_provider())
    results = service.run_due_monitors()
    checked_ids = {str(monitor_id) for monitor_id, _ in results}

    assert daily_id in checked_ids
    assert manual_id not in checked_ids
