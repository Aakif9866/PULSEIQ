def test_health_check_does_not_require_db():
    # Imported lazily so this test never needs a live DB connection.
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as client:
        response = client.get("/api/v1/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    # Non-sensitive — just "local" or "r2", never credentials — so the
    # frontend can show an accurate storage-persistence note.
    assert body["storage_provider"] in ("local", "r2")


def test_every_response_carries_a_request_id():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as client:
        response = client.get("/api/v1/health")

    request_id = response.headers.get("x-request-id")
    assert request_id
    # Two requests never share an id.
    with TestClient(app) as client:
        other = client.get("/api/v1/health")
    assert other.headers.get("x-request-id") != request_id
