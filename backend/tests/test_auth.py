def test_signup_then_login(client):
    signup_resp = client.post(
        "/api/v1/auth/signup",
        json={
            "email": "analyst@pulseiq.dev",
            "password": "correct-horse-1",
            "full_name": "Ana Lyst",
        },
    )
    assert signup_resp.status_code == 201
    body = signup_resp.json()
    assert body["user"]["email"] == "analyst@pulseiq.dev"
    assert "access_token" in body["tokens"]

    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "analyst@pulseiq.dev", "password": "correct-horse-1"},
    )
    assert login_resp.status_code == 200
    access_token = login_resp.json()["tokens"]["access_token"]

    me_resp = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {access_token}"}
    )
    assert me_resp.status_code == 200
    assert me_resp.json()["email"] == "analyst@pulseiq.dev"


def test_signup_duplicate_email_rejected(client):
    payload = {"email": "dup@pulseiq.dev", "password": "correct-horse-1"}
    first = client.post("/api/v1/auth/signup", json=payload)
    assert first.status_code == 201

    second = client.post("/api/v1/auth/signup", json=payload)
    assert second.status_code == 409


def test_login_wrong_password_rejected(client):
    client.post(
        "/api/v1/auth/signup",
        json={"email": "wrongpass@pulseiq.dev", "password": "correct-horse-1"},
    )
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "wrongpass@pulseiq.dev", "password": "not-the-password"},
    )
    assert resp.status_code == 401


def test_me_requires_auth(client):
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 401
