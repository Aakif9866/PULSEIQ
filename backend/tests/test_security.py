"""Release-audit fixes: rate limits, refresh-token rotation/revocation,
account export/deletion, password limits, security headers, early 413s,
AI metering on /ask-sql, the app-wide AI cap, and the demo upload rotation."""
from types import SimpleNamespace

import pytest

from app.core import rate_limit
from app.core.config import settings

PASSWORD = "correct-horse-1"
_SQL_GEN = "app.services.analyst_service.build_sql_from_question"


@pytest.fixture(autouse=True)
def _local_storage_root(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "LOCAL_STORAGE_ROOT", str(tmp_path))


def _signup(client, email: str, password: str = PASSWORD) -> dict:
    resp = client.post("/api/v1/auth/signup", json={"email": email, "password": password})
    assert resp.status_code == 201, resp.text
    return resp.json()["tokens"]


def _auth(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def _upload(client, headers, name="a.csv", body=b"id,amount\n1,10\n2,20\n"):
    files = {"file": (name, body, "text/csv")}
    return client.post("/api/v1/datasets", headers=headers, files=files)


# ---- rate limits ----

def test_login_is_rate_limited_per_ip(client, monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    rate_limit.reset()
    body = {"email": "nobody@pulseiq.dev", "password": "wrong-password"}
    codes = [client.post("/api/v1/auth/login", json=body).status_code for _ in range(11)]
    assert codes[:10] == [401] * 10
    assert codes[10] == 429


def test_client_ip_uses_proxy_appended_entry_not_spoofable_one(monkeypatch):
    monkeypatch.setattr(settings, "TRUSTED_PROXY_HOPS", 1)
    request = SimpleNamespace(
        headers={"x-forwarded-for": "6.6.6.6, 203.0.113.9"}, client=SimpleNamespace(host="10.0.0.1")
    )
    assert rate_limit.client_ip(request) == "203.0.113.9"  # type: ignore[arg-type]
    monkeypatch.setattr(settings, "TRUSTED_PROXY_HOPS", 0)
    assert rate_limit.client_ip(request) == "10.0.0.1"  # type: ignore[arg-type]


# ---- refresh tokens ----

def test_refresh_rotates_and_reuse_revokes_every_session(client):
    tokens = _signup(client, "rotate@pulseiq.dev")
    first = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert first.status_code == 200
    rotated = first.json()
    assert rotated["refresh_token"] != tokens["refresh_token"]

    # Replaying the used token is treated as theft: it fails and kills the new one too.
    replay = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert replay.status_code == 401
    after = client.post("/api/v1/auth/refresh", json={"refresh_token": rotated["refresh_token"]})
    assert after.status_code == 401


def test_logout_revokes_refresh_token(client):
    tokens = _signup(client, "logout@pulseiq.dev")
    out = client.post("/api/v1/auth/logout", json={"refresh_token": tokens["refresh_token"]})
    assert out.status_code == 204
    resp = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert resp.status_code == 401


def test_access_token_cannot_be_used_as_refresh_token(client):
    tokens = _signup(client, "wrongtype@pulseiq.dev")
    resp = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["access_token"]})
    assert resp.status_code == 401


# ---- passwords ----

def test_signup_rejects_password_over_bcrypt_limit(client):
    resp = client.post(
        "/api/v1/auth/signup", json={"email": "long@pulseiq.dev", "password": "a" * 73}
    )
    assert resp.status_code == 422


def test_login_unknown_email_and_wrong_password_look_identical(client):
    _signup(client, "known@pulseiq.dev")
    unknown = client.post(
        "/api/v1/auth/login", json={"email": "unknown@pulseiq.dev", "password": "whatever-1"}
    )
    wrong = client.post(
        "/api/v1/auth/login", json={"email": "known@pulseiq.dev", "password": "whatever-1"}
    )
    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json() == wrong.json()


# ---- account export / deletion ----

def test_export_contains_only_my_data(client):
    mine = _auth(_signup(client, "exporter@pulseiq.dev"))
    other = _auth(_signup(client, "other-export@pulseiq.dev"))
    assert _upload(client, mine, "mine.csv").status_code == 201
    assert _upload(client, other, "theirs.csv").status_code == 201

    resp = client.get("/api/v1/auth/me/export", headers=mine)
    assert resp.status_code == 200
    assert "attachment" in resp.headers["content-disposition"]
    data = resp.json()
    assert data["user"]["email"] == "exporter@pulseiq.dev"
    assert [d["original_filename"] for d in data["datasets"]] == ["mine.csv"]
    assert "hashed_password" not in str(data)


def test_delete_account_requires_password_and_removes_files(client, tmp_path):
    tokens = _signup(client, "leaver@pulseiq.dev")
    headers = _auth(tokens)
    assert _upload(client, headers).status_code == 201
    assert any(p.is_file() for p in tmp_path.rglob("*"))

    wrong = client.request(
        "DELETE", "/api/v1/auth/me", headers=headers, json={"password": "not-it-123"}
    )
    assert wrong.status_code == 403

    ok = client.request("DELETE", "/api/v1/auth/me", headers=headers, json={"password": PASSWORD})
    assert ok.status_code == 204
    assert not any(p.is_file() for p in tmp_path.rglob("*"))
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401
    login = client.post(
        "/api/v1/auth/login", json={"email": "leaver@pulseiq.dev", "password": PASSWORD}
    )
    assert login.status_code == 401


def test_demo_account_cannot_be_deleted(client, monkeypatch):
    monkeypatch.setattr(settings, "DEMO_USER_EMAIL", "demo-del@pulseiq.dev")
    headers = _auth(_signup(client, "demo-del@pulseiq.dev"))
    resp = client.request("DELETE", "/api/v1/auth/me", headers=headers, json={"password": PASSWORD})
    assert resp.status_code == 403


# ---- uploads ----

def test_demo_account_drops_its_oldest_upload_instead_of_locking_out(client, monkeypatch):
    from app.demo import DEMO_FILENAME

    monkeypatch.setattr(settings, "DEMO_USER_EMAIL", "demo-rot@pulseiq.dev")
    monkeypatch.setattr(settings, "MAX_DATASETS_PER_USER", 2)
    headers = _auth(_signup(client, "demo-rot@pulseiq.dev"))
    assert _upload(client, headers, DEMO_FILENAME).status_code == 201
    assert _upload(client, headers, "first.csv").status_code == 201
    assert _upload(client, headers, "second.csv").status_code == 201

    listed = client.get("/api/v1/datasets", headers=headers).json()
    names = sorted(d["original_filename"] for d in listed)
    assert names == sorted([DEMO_FILENAME, "second.csv"])  # sample kept, oldest upload dropped


def test_declared_oversized_body_rejected_before_parsing(client, monkeypatch):
    monkeypatch.setattr(settings, "MAX_UPLOAD_SIZE_MB", 1)
    headers = _auth(_signup(client, "bigbody@pulseiq.dev"))
    resp = client.post(
        "/api/v1/datasets",
        headers={**headers, "Content-Type": "multipart/form-data; boundary=x"},
        content=b"x" * (2 * 1024 * 1024 + 10),
    )
    assert resp.status_code == 413
    assert "1 MB" in resp.json()["detail"]


# ---- headers ----

def test_security_headers_on_responses(client):
    resp = client.get("/api/v1/health")
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert resp.headers["X-Frame-Options"] == "DENY"
    assert resp.headers["Referrer-Policy"] == "no-referrer"
    assert "frame-ancestors 'none'" in resp.headers["Content-Security-Policy"]


# ---- AI metering and caps ----

def _fake_sql_with_usage(*_a, **_kw):
    from app.ai.groq_client import note_usage

    note_usage(SimpleNamespace(usage=SimpleNamespace(prompt_tokens=100, completion_tokens=20)))
    return "SELECT id FROM dataset"


def test_ask_sql_tokens_count_toward_the_quota(client, monkeypatch):
    monkeypatch.setattr(settings, "AI_PROVIDER", "groq")
    monkeypatch.setattr(settings, "AI_DAILY_TOKEN_QUOTA_PER_USER", 200)
    monkeypatch.setattr(_SQL_GEN, _fake_sql_with_usage)
    monkeypatch.setattr("app.services.analyst_service.summarize_result", lambda *_a: "ok")
    headers = _auth(_signup(client, "metered@pulseiq.dev"))
    dataset_id = _upload(client, headers).json()["id"]

    url = f"/api/v1/datasets/{dataset_id}/ask-sql"
    assert client.post(url, headers=headers, json={"question": "q"}).status_code == 200
    assert client.get("/api/v1/usage/me", headers=headers).json()["total_tokens"] == 120
    assert client.post(url, headers=headers, json={"question": "q"}).status_code == 200
    # 240 >= 200: the third call is blocked, which was impossible before metering.
    assert client.post(url, headers=headers, json={"question": "q"}).status_code == 429


def test_global_ai_cap_blocks_everyone(client, monkeypatch):
    monkeypatch.setattr(settings, "AI_PROVIDER", "groq")
    monkeypatch.setattr(settings, "AI_DAILY_TOKEN_QUOTA_GLOBAL", 100)
    monkeypatch.setattr(_SQL_GEN, _fake_sql_with_usage)
    monkeypatch.setattr("app.services.analyst_service.summarize_result", lambda *_a: "ok")
    spender = _auth(_signup(client, "spender@pulseiq.dev"))
    bystander = _auth(_signup(client, "bystander@pulseiq.dev"))
    ds1 = _upload(client, spender).json()["id"]
    ds2 = _upload(client, bystander).json()["id"]

    assert client.post(
        f"/api/v1/datasets/{ds1}/ask-sql", headers=spender, json={"question": "q"}
    ).status_code == 200
    url2 = f"/api/v1/datasets/{ds2}/ask-sql"
    blocked = client.post(url2, headers=bystander, json={"question": "q"})
    assert blocked.status_code == 429
    assert "everyone" in blocked.json()["detail"]


def test_conversation_turns_are_length_capped(client):
    headers = _auth(_signup(client, "longturn@pulseiq.dev"))
    dataset_id = _upload(client, headers).json()["id"]
    resp = client.post(
        f"/api/v1/datasets/{dataset_id}/analyze",
        headers=headers,
        json={"question": "q", "conversation_history": [{"question": "q", "answer": "x" * 4001}]},
    )
    assert resp.status_code == 422
