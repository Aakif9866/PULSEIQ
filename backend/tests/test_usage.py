"""Per-user AI usage recording and daily token quotas — docs/PHASES.md
Phase 8 step 4. run_analysis is monkeypatched (no real Groq call); a fake
provider-side token count is injected by patching UsageTrackingProvider's
totals, so the quota math runs against real numbers in the real database
table, not a mock of the repository.
"""
from datetime import UTC, datetime, timedelta

import pytest

from app.ai.providers.usage_tracking import UsageTrackingProvider
from app.core.config import settings
from app.schemas.analysis import AnalyzeResponse
from app.services import deep_analysis_service, usage_service

SALES_CSV = b"region,amount\neast,10\neast,30\nwest,5\n"


@pytest.fixture(autouse=True)
def _ai_enabled_and_clean_cache(monkeypatch):
    monkeypatch.setattr(settings, "AI_PROVIDER", "groq")
    monkeypatch.setattr(settings, "AI_DAILY_TOKEN_QUOTA_PER_USER", None)
    yield
    deep_analysis_service._answer_cache.clear()


def _signup(client, email: str) -> dict[str, str]:
    resp = client.post("/api/v1/auth/signup", json={"email": email, "password": "correct-horse-1"})
    return {"Authorization": f"Bearer {resp.json()['tokens']['access_token']}"}


def _upload(client, headers) -> str:
    resp = client.post(
        "/api/v1/datasets", headers=headers, files={"file": ("s.csv", SALES_CSV, "text/csv")}
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def _fake_analysis_spending(tokens: int, status: str = "ok"):
    """A run_analysis stand-in that makes the (real) UsageTrackingProvider
    report `tokens` spent, exactly as a real multi-call tool loop would."""

    def _run(df, provider, question, conversation_history=None):
        assert isinstance(provider, UsageTrackingProvider)
        provider.totals.call_count = 2
        provider.totals.prompt_tokens = tokens - 100
        provider.totals.completion_tokens = 100
        provider.totals.total_tokens = tokens
        return AnalyzeResponse(question=question, answer="An answer.", status=status)

    return _run


def _analyze(client, headers, dataset_id, question="How many rows?"):
    return client.post(
        f"/api/v1/datasets/{dataset_id}/analyze", headers=headers, json={"question": question}
    )


# ---- recording ----


def test_an_analyze_call_is_recorded_and_shows_up_in_usage(client, monkeypatch):
    monkeypatch.setattr(
        "app.services.deep_analysis_service.run_analysis", _fake_analysis_spending(1_500)
    )
    headers = _signup(client, "usage-record@pulseiq.dev")
    dataset_id = _upload(client, headers)

    assert _analyze(client, headers, dataset_id).status_code == 200

    usage = client.get("/api/v1/usage/me", headers=headers).json()
    assert usage["requests"] == 1
    assert usage["total_tokens"] == 1_500
    assert usage["prompt_tokens"] == 1_400
    assert usage["completion_tokens"] == 100
    assert usage["cache_hits"] == 0


def test_a_cache_hit_is_recorded_with_zero_tokens(client, monkeypatch):
    monkeypatch.setattr(
        "app.services.deep_analysis_service.run_analysis", _fake_analysis_spending(1_500)
    )
    headers = _signup(client, "usage-cachehit@pulseiq.dev")
    dataset_id = _upload(client, headers)

    _analyze(client, headers, dataset_id)
    _analyze(client, headers, dataset_id)  # same question -> served from cache

    usage = client.get("/api/v1/usage/me", headers=headers).json()
    assert usage["requests"] == 2
    assert usage["cache_hits"] == 1
    assert usage["total_tokens"] == 1_500  # the cache hit added nothing


def test_usage_is_scoped_to_the_requesting_user(client, monkeypatch):
    monkeypatch.setattr(
        "app.services.deep_analysis_service.run_analysis", _fake_analysis_spending(1_500)
    )
    alice = _signup(client, "usage-alice@pulseiq.dev")
    bob = _signup(client, "usage-bob@pulseiq.dev")
    _analyze(client, alice, _upload(client, alice))

    assert client.get("/api/v1/usage/me", headers=bob).json()["total_tokens"] == 0


def test_cost_is_reported_as_unknown_not_zero_when_pricing_is_unset(client, monkeypatch):
    monkeypatch.setattr(settings, "GROQ_INPUT_COST_PER_1M_TOKENS", None)
    monkeypatch.setattr(settings, "GROQ_OUTPUT_COST_PER_1M_TOKENS", None)
    monkeypatch.setattr(
        "app.services.deep_analysis_service.run_analysis", _fake_analysis_spending(1_500)
    )
    headers = _signup(client, "usage-nocost@pulseiq.dev")
    _analyze(client, headers, _upload(client, headers))

    usage = client.get("/api/v1/usage/me", headers=headers).json()
    assert usage["estimated_cost_usd"] is None
    assert usage["cost_tracking_configured"] is False


def test_cost_is_computed_when_pricing_is_configured(client, monkeypatch):
    monkeypatch.setattr(settings, "GROQ_INPUT_COST_PER_1M_TOKENS", 1.0)
    monkeypatch.setattr(settings, "GROQ_OUTPUT_COST_PER_1M_TOKENS", 2.0)
    monkeypatch.setattr(
        "app.services.deep_analysis_service.run_analysis", _fake_analysis_spending(1_000_100)
    )
    headers = _signup(client, "usage-cost@pulseiq.dev")
    _analyze(client, headers, _upload(client, headers))

    usage = client.get("/api/v1/usage/me", headers=headers).json()
    # 1,000,000 prompt tokens @ $1/1M + 100 completion tokens @ $2/1M
    assert usage["estimated_cost_usd"] == pytest.approx(1.0 + 0.0002)
    assert usage["cost_tracking_configured"] is True


def test_usage_requires_auth(client):
    assert client.get("/api/v1/usage/me").status_code == 401


# ---- quota ----


def test_no_quota_configured_means_no_limit_is_ever_enforced(client, monkeypatch):
    monkeypatch.setattr(
        "app.services.deep_analysis_service.run_analysis", _fake_analysis_spending(10_000_000)
    )
    headers = _signup(client, "usage-noquota@pulseiq.dev")
    dataset_id = _upload(client, headers)

    assert _analyze(client, headers, dataset_id, "q1").status_code == 200
    assert _analyze(client, headers, dataset_id, "q2").status_code == 200
    usage = client.get("/api/v1/usage/me", headers=headers).json()
    assert usage["quota_tokens"] is None
    assert usage["remaining_tokens"] is None


def test_request_under_quota_is_allowed(client, monkeypatch):
    monkeypatch.setattr(settings, "AI_DAILY_TOKEN_QUOTA_PER_USER", 5_000)
    monkeypatch.setattr(
        "app.services.deep_analysis_service.run_analysis", _fake_analysis_spending(1_500)
    )
    headers = _signup(client, "usage-under@pulseiq.dev")
    dataset_id = _upload(client, headers)

    assert _analyze(client, headers, dataset_id).status_code == 200
    assert client.get("/api/v1/usage/me", headers=headers).json()["remaining_tokens"] == 3_500


def test_request_over_quota_is_rejected_with_a_clear_429(client, monkeypatch):
    monkeypatch.setattr(settings, "AI_DAILY_TOKEN_QUOTA_PER_USER", 2_000)
    monkeypatch.setattr(
        "app.services.deep_analysis_service.run_analysis", _fake_analysis_spending(2_500)
    )
    headers = _signup(client, "usage-over@pulseiq.dev")
    dataset_id = _upload(client, headers)

    # The first request is allowed (0 used so far) and spends past the quota...
    assert _analyze(client, headers, dataset_id, "q1").status_code == 200
    # ...so the next real (non-cached) one is refused.
    resp = _analyze(client, headers, dataset_id, "q2")
    assert resp.status_code == 429
    assert "Daily AI usage limit reached" in resp.json()["detail"]
    assert "2,500 of 2,000 tokens" in resp.json()["detail"]
    assert "Resets at" in resp.json()["detail"]


def test_a_cached_answer_is_still_served_to_a_user_over_quota(client, monkeypatch):
    monkeypatch.setattr(settings, "AI_DAILY_TOKEN_QUOTA_PER_USER", 2_000)
    monkeypatch.setattr(
        "app.services.deep_analysis_service.run_analysis", _fake_analysis_spending(2_500)
    )
    headers = _signup(client, "usage-cached-over@pulseiq.dev")
    dataset_id = _upload(client, headers)

    _analyze(client, headers, dataset_id, "q1")  # now over quota
    # Same question again — it's cached, costs nothing, so it's served.
    assert _analyze(client, headers, dataset_id, "q1").status_code == 200


def test_quota_also_blocks_ask_and_ask_sql_so_it_cannot_be_bypassed(client, monkeypatch):
    monkeypatch.setattr(settings, "AI_DAILY_TOKEN_QUOTA_PER_USER", 2_000)
    monkeypatch.setattr(
        "app.services.deep_analysis_service.run_analysis", _fake_analysis_spending(2_500)
    )
    headers = _signup(client, "usage-bypass@pulseiq.dev")
    dataset_id = _upload(client, headers)
    _analyze(client, headers, dataset_id)  # now over quota

    for endpoint in ("ask", "ask-sql"):
        resp = client.post(
            f"/api/v1/datasets/{dataset_id}/{endpoint}",
            headers=headers,
            json={"question": "anything"},
        )
        assert resp.status_code == 429, endpoint


def test_quota_resets_at_the_next_utc_midnight(client, monkeypatch):
    monkeypatch.setattr(settings, "AI_DAILY_TOKEN_QUOTA_PER_USER", 2_000)
    monkeypatch.setattr(
        "app.services.deep_analysis_service.run_analysis", _fake_analysis_spending(2_500)
    )
    headers = _signup(client, "usage-reset@pulseiq.dev")
    dataset_id = _upload(client, headers)
    _analyze(client, headers, dataset_id, "q1")  # over quota today
    assert _analyze(client, headers, dataset_id, "q2").status_code == 429

    tomorrow = datetime.now(UTC) + timedelta(days=1)
    monkeypatch.setattr(usage_service, "_now", lambda: tomorrow)
    assert _analyze(client, headers, dataset_id, "q3").status_code == 200


def test_deleting_a_dataset_does_not_reset_the_owners_quota(client, monkeypatch):
    # ai_usage_log.dataset_id is ON DELETE SET NULL, not CASCADE (migration
    # 0009) — otherwise delete-and-re-upload would wipe the day's spend.
    monkeypatch.setattr(settings, "AI_DAILY_TOKEN_QUOTA_PER_USER", 2_000)
    monkeypatch.setattr(
        "app.services.deep_analysis_service.run_analysis", _fake_analysis_spending(2_500)
    )
    headers = _signup(client, "usage-delete@pulseiq.dev")
    first = _upload(client, headers)
    _analyze(client, headers, first)

    assert client.delete(f"/api/v1/datasets/{first}", headers=headers).status_code == 204
    second = _upload(client, headers)
    assert _analyze(client, headers, second).status_code == 429
