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


SALES_CSV = b"region,amount\neast,10\neast,30\nwest,5\n"


def _upload_sales(client, headers) -> str:
    resp = client.post(
        "/api/v1/datasets",
        headers=headers,
        files={"file": ("sales.csv", SALES_CSV, "text/csv")},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def _chart_payload(dataset_id: str, title: str = "Total by region") -> dict:
    return {
        "dataset_id": dataset_id,
        "title": title,
        "chart_type": "bar",
        "query": {
            "group_by": ["region"],
            "aggregations": [{"op": "sum", "column": "amount", "alias": "total"}],
            "sort_by": "region",
        },
    }


def test_create_dashboard_and_add_chart(client):
    token = _signup_and_token(client, "dashboarder@pulseiq.dev")
    headers = {"Authorization": f"Bearer {token}"}
    dataset_id = _upload_sales(client, headers)

    dash_resp = client.post("/api/v1/dashboards", headers=headers, json={"name": "Sales overview"})
    assert dash_resp.status_code == 201
    dashboard_id = dash_resp.json()["id"]
    assert dash_resp.json()["chart_count"] == 0

    chart_resp = client.post(
        f"/api/v1/dashboards/{dashboard_id}/charts",
        headers=headers,
        json=_chart_payload(dataset_id),
    )
    assert chart_resp.status_code == 201
    chart_body = chart_resp.json()
    assert chart_body["dataset_filename"] == "sales.csv"
    assert chart_body["position"] == 0

    list_resp = client.get("/api/v1/dashboards", headers=headers)
    assert list_resp.json()[0]["chart_count"] == 1

    detail_resp = client.get(f"/api/v1/dashboards/{dashboard_id}", headers=headers)
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["name"] == "Sales overview"
    assert len(detail["charts"]) == 1
    assert detail["charts"][0]["title"] == "Total by region"


def test_chart_ordering_and_move(client):
    token = _signup_and_token(client, "reorderer@pulseiq.dev")
    headers = {"Authorization": f"Bearer {token}"}
    dataset_id = _upload_sales(client, headers)
    dashboard_id = client.post(
        "/api/v1/dashboards", headers=headers, json={"name": "Board"}
    ).json()["id"]

    first = client.post(
        f"/api/v1/dashboards/{dashboard_id}/charts",
        headers=headers,
        json=_chart_payload(dataset_id, "First"),
    ).json()
    second = client.post(
        f"/api/v1/dashboards/{dashboard_id}/charts",
        headers=headers,
        json=_chart_payload(dataset_id, "Second"),
    ).json()

    detail = client.get(f"/api/v1/dashboards/{dashboard_id}", headers=headers).json()
    assert [c["title"] for c in detail["charts"]] == ["First", "Second"]

    move_resp = client.post(
        f"/api/v1/dashboards/{dashboard_id}/charts/{second['id']}/move",
        headers=headers,
        json={"direction": "up"},
    )
    assert move_resp.status_code == 204

    detail = client.get(f"/api/v1/dashboards/{dashboard_id}", headers=headers).json()
    assert [c["title"] for c in detail["charts"]] == ["Second", "First"]

    # Already at the top: moving up again is a no-op, not an error.
    noop_resp = client.post(
        f"/api/v1/dashboards/{dashboard_id}/charts/{second['id']}/move",
        headers=headers,
        json={"direction": "up"},
    )
    assert noop_resp.status_code == 204
    detail = client.get(f"/api/v1/dashboards/{dashboard_id}", headers=headers).json()
    assert [c["title"] for c in detail["charts"]] == ["Second", "First"]

    assert first["id"]  # sanity: first chart's id was captured


def test_delete_chart_and_dashboard(client):
    token = _signup_and_token(client, "remover@pulseiq.dev")
    headers = {"Authorization": f"Bearer {token}"}
    dataset_id = _upload_sales(client, headers)
    dashboard_id = client.post(
        "/api/v1/dashboards", headers=headers, json={"name": "Board"}
    ).json()["id"]
    chart_id = client.post(
        f"/api/v1/dashboards/{dashboard_id}/charts",
        headers=headers,
        json=_chart_payload(dataset_id),
    ).json()["id"]

    delete_chart_resp = client.delete(
        f"/api/v1/dashboards/{dashboard_id}/charts/{chart_id}", headers=headers
    )
    assert delete_chart_resp.status_code == 204

    detail = client.get(f"/api/v1/dashboards/{dashboard_id}", headers=headers).json()
    assert detail["charts"] == []

    delete_dash_resp = client.delete(f"/api/v1/dashboards/{dashboard_id}", headers=headers)
    assert delete_dash_resp.status_code == 204

    get_resp = client.get(f"/api/v1/dashboards/{dashboard_id}", headers=headers)
    assert get_resp.status_code == 404


def test_cannot_add_chart_for_another_users_dataset(client):
    owner_token = _signup_and_token(client, "chart-owner@pulseiq.dev")
    dataset_id = _upload_sales(client, {"Authorization": f"Bearer {owner_token}"})

    intruder_token = _signup_and_token(client, "chart-intruder@pulseiq.dev")
    intruder_headers = {"Authorization": f"Bearer {intruder_token}"}
    dashboard_id = client.post(
        "/api/v1/dashboards", headers=intruder_headers, json={"name": "Intruder board"}
    ).json()["id"]

    resp = client.post(
        f"/api/v1/dashboards/{dashboard_id}/charts",
        headers=intruder_headers,
        json=_chart_payload(dataset_id),
    )
    assert resp.status_code == 404


def test_cannot_access_another_users_dashboard(client):
    owner_token = _signup_and_token(client, "board-owner@pulseiq.dev")
    dashboard_id = client.post(
        "/api/v1/dashboards",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"name": "Private board"},
    ).json()["id"]

    intruder_token = _signup_and_token(client, "board-intruder@pulseiq.dev")
    resp = client.get(
        f"/api/v1/dashboards/{dashboard_id}",
        headers={"Authorization": f"Bearer {intruder_token}"},
    )
    assert resp.status_code == 404


def test_dashboards_require_auth(client):
    resp = client.get("/api/v1/dashboards")
    assert resp.status_code == 401
