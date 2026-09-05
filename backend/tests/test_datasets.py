import pytest

from app.core.config import settings


@pytest.fixture(autouse=True)
def _local_storage_root(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "LOCAL_STORAGE_ROOT", str(tmp_path))


def _stored_files(tmp_path) -> list:
    return [p for p in tmp_path.rglob("*") if p.is_file()]


def _signup_and_token(client, email: str) -> str:
    resp = client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "correct-horse-1"},
    )
    return resp.json()["tokens"]["access_token"]


def test_upload_dataset(client):
    token = _signup_and_token(client, "uploader@pulseiq.dev")
    csv_bytes = b"id,amount\n1,10\n2,20\n"

    resp = client.post(
        "/api/v1/datasets",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("sales.csv", csv_bytes, "text/csv")},
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["original_filename"] == "sales.csv"
    # Profiling (Phase 3) runs synchronously right after upload, so a valid
    # CSV is already "profiled" by the time this response comes back.
    assert body["status"] == "profiled"
    assert body["size_bytes"] == len(csv_bytes)


def test_upload_rejects_unsupported_extension(client):
    token = _signup_and_token(client, "badfile@pulseiq.dev")

    resp = client.post(
        "/api/v1/datasets",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("malware.exe", b"whatever", "application/octet-stream")},
    )

    assert resp.status_code == 415


def test_upload_requires_auth(client):
    resp = client.post(
        "/api/v1/datasets",
        files={"file": ("sales.csv", b"a,b\n1,2\n", "text/csv")},
    )
    assert resp.status_code == 401


def test_list_and_get_dataset(client):
    token = _signup_and_token(client, "lister@pulseiq.dev")
    headers = {"Authorization": f"Bearer {token}"}

    upload_resp = client.post(
        "/api/v1/datasets",
        headers=headers,
        files={"file": ("sales.csv", b"id,amount\n1,10\n", "text/csv")},
    )
    dataset_id = upload_resp.json()["id"]

    list_resp = client.get("/api/v1/datasets", headers=headers)
    assert list_resp.status_code == 200
    assert any(dataset["id"] == dataset_id for dataset in list_resp.json())

    get_resp = client.get(f"/api/v1/datasets/{dataset_id}", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["original_filename"] == "sales.csv"


def test_get_unknown_dataset_returns_404(client):
    token = _signup_and_token(client, "seeker@pulseiq.dev")
    resp = client.get(
        "/api/v1/datasets/00000000-0000-0000-0000-000000000000",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


def test_cannot_access_another_users_dataset(client):
    owner_token = _signup_and_token(client, "owner@pulseiq.dev")
    upload_resp = client.post(
        "/api/v1/datasets",
        headers={"Authorization": f"Bearer {owner_token}"},
        files={"file": ("secret.csv", b"a,b\n1,2\n", "text/csv")},
    )
    dataset_id = upload_resp.json()["id"]

    intruder_token = _signup_and_token(client, "intruder@pulseiq.dev")
    resp = client.get(
        f"/api/v1/datasets/{dataset_id}",
        headers={"Authorization": f"Bearer {intruder_token}"},
    )
    assert resp.status_code == 404


def test_delete_requires_auth(client):
    resp = client.delete("/api/v1/datasets/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 401


def test_delete_unknown_dataset_returns_404(client):
    token = _signup_and_token(client, "deleter-unknown@pulseiq.dev")
    resp = client.delete(
        "/api/v1/datasets/00000000-0000-0000-0000-000000000000",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


def test_delete_removes_metadata_and_the_stored_file(client, tmp_path):
    token = _signup_and_token(client, "deleter@pulseiq.dev")
    headers = {"Authorization": f"Bearer {token}"}

    upload_resp = client.post(
        "/api/v1/datasets",
        headers=headers,
        files={"file": ("to-delete.csv", b"a,b\n1,2\n", "text/csv")},
    )
    dataset_id = upload_resp.json()["id"]
    assert len(_stored_files(tmp_path)) == 1

    delete_resp = client.delete(f"/api/v1/datasets/{dataset_id}", headers=headers)
    assert delete_resp.status_code == 204

    # Metadata is gone...
    get_resp = client.get(f"/api/v1/datasets/{dataset_id}", headers=headers)
    assert get_resp.status_code == 404
    # ...and so is the file on disk, not just the DB row.
    assert _stored_files(tmp_path) == []


def test_cannot_delete_another_users_dataset(client, tmp_path):
    owner_token = _signup_and_token(client, "delete-owner@pulseiq.dev")
    upload_resp = client.post(
        "/api/v1/datasets",
        headers={"Authorization": f"Bearer {owner_token}"},
        files={"file": ("protected.csv", b"a,b\n1,2\n", "text/csv")},
    )
    dataset_id = upload_resp.json()["id"]

    intruder_token = _signup_and_token(client, "delete-intruder@pulseiq.dev")
    resp = client.delete(
        f"/api/v1/datasets/{dataset_id}",
        headers={"Authorization": f"Bearer {intruder_token}"},
    )
    assert resp.status_code == 404

    # The real owner's dataset and its file are both untouched.
    get_resp = client.get(
        f"/api/v1/datasets/{dataset_id}", headers={"Authorization": f"Bearer {owner_token}"}
    )
    assert get_resp.status_code == 200
    assert len(_stored_files(tmp_path)) == 1


def test_deleting_dataset_cascades_to_insights_and_dashboard_charts(client):
    token = _signup_and_token(client, "cascade@pulseiq.dev")
    headers = {"Authorization": f"Bearer {token}"}

    upload_resp = client.post(
        "/api/v1/datasets",
        headers=headers,
        files={"file": ("cascade.csv", b"a,b\n1,2\n", "text/csv")},
    )
    dataset_id = upload_resp.json()["id"]

    query = {"aggregations": [{"op": "count"}]}
    client.post(
        "/api/v1/insights",
        headers=headers,
        json={
            "dataset_id": dataset_id,
            "question": "q",
            "answer": "a",
            "query": query,
            "row_count": 1,
        },
    )
    dashboard_id = client.post(
        "/api/v1/dashboards", headers=headers, json={"name": "Board"}
    ).json()["id"]
    client.post(
        f"/api/v1/dashboards/{dashboard_id}/charts",
        headers=headers,
        json={"dataset_id": dataset_id, "title": "t", "chart_type": "bar", "query": query},
    )

    delete_resp = client.delete(f"/api/v1/datasets/{dataset_id}", headers=headers)
    assert delete_resp.status_code == 204

    assert client.get("/api/v1/insights", headers=headers).json() == []
    assert client.get(f"/api/v1/dashboards/{dashboard_id}", headers=headers).json()["charts"] == []


def test_upload_cleans_up_the_file_if_the_db_write_fails(db_session, tmp_path, monkeypatch):
    """If the DB insert fails after the file's already been saved, the file
    must not be left behind as an orphan with nothing referencing it.

    Exercised at the service layer directly rather than over HTTP: a raw
    (non-HTTPException) exception escaping through Starlette's
    BaseHTTPMiddleware (our request-logging middleware) hits a known
    TestClient/anyio task-group interaction that isn't about this feature —
    the service layer is exactly where this cleanup actually lives."""
    import uuid

    from app.repositories.dataset_repository import DatasetRepository
    from app.services.dataset_service import DatasetService
    from app.storage.local import LocalStorageProvider

    def _boom(self, **kwargs):
        raise RuntimeError("simulated DB failure")

    monkeypatch.setattr(DatasetRepository, "create", _boom)

    storage = LocalStorageProvider(str(tmp_path))
    service = DatasetService(db_session, storage)

    with pytest.raises(RuntimeError, match="simulated DB failure"):
        service.upload(
            owner_id=uuid.uuid4(),
            filename="orphan.csv",
            content_type="text/csv",
            data=b"a,b\n1,2\n",
        )

    assert _stored_files(tmp_path) == []
