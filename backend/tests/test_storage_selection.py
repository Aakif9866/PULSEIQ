import pytest

from app.core.config import settings
from app.storage import get_storage_provider


def test_r2_rejects_public_r2_dev_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "STORAGE_PROVIDER", "r2")
    for name in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET_NAME"):
        monkeypatch.setattr(settings, name, "x")
    monkeypatch.setattr(settings, "R2_ENDPOINT_URL", "https://pub-abc123.r2.dev")
    with pytest.raises(RuntimeError, match="r2.dev"):
        get_storage_provider()
