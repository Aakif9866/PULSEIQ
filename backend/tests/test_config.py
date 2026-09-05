import pytest

from app.core.config import Settings


def test_production_rejects_default_secret_key():
    with pytest.raises(ValueError, match="SECRET_KEY"):
        Settings(ENVIRONMENT="production", SECRET_KEY="insecure-dev-secret-change-me", DEBUG=False)


def test_production_rejects_debug_true():
    with pytest.raises(ValueError, match="DEBUG"):
        Settings(ENVIRONMENT="production", SECRET_KEY="a-real-unique-secret", DEBUG=True)


def test_production_accepts_a_real_secret_with_debug_off():
    settings = Settings(ENVIRONMENT="production", SECRET_KEY="a-real-unique-secret", DEBUG=False)
    assert settings.ENVIRONMENT == "production"


def test_development_allows_the_default_secret_key(monkeypatch):
    # Isolate from whatever's in the ambient environment — CI's own job
    # sets a real SECRET_KEY for every step (including this test), which
    # pydantic-settings would otherwise read ahead of the class default,
    # since env vars outrank it for any field not passed explicitly here.
    monkeypatch.delenv("SECRET_KEY", raising=False)
    settings = Settings(ENVIRONMENT="development")
    assert settings.SECRET_KEY == "insecure-dev-secret-change-me"
