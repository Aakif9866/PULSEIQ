"""Storage provider selection.

Callers should depend on get_storage_provider() (or the StorageProvider
type) rather than importing a concrete provider directly, so
STORAGE_PROVIDER stays the single switch between local dev storage and R2.
"""
from app.core.config import settings
from app.storage.base import StorageProvider
from app.storage.local import LocalStorageProvider

__all__ = ["StorageProvider", "get_storage_provider"]


def get_storage_provider() -> StorageProvider:
    if settings.STORAGE_PROVIDER == "r2":
        from app.storage.r2 import R2StorageProvider  # local import: boto3 client is R2-only

        missing = [
            name
            for name, value in [
                ("R2_ACCOUNT_ID", settings.R2_ACCOUNT_ID),
                ("R2_ACCESS_KEY_ID", settings.R2_ACCESS_KEY_ID),
                ("R2_SECRET_ACCESS_KEY", settings.R2_SECRET_ACCESS_KEY),
                ("R2_BUCKET_NAME", settings.R2_BUCKET_NAME),
            ]
            if not value
        ]
        if missing:
            raise RuntimeError(f"STORAGE_PROVIDER=r2 requires {', '.join(missing)} to be set")

        return R2StorageProvider(
            account_id=settings.R2_ACCOUNT_ID,  # type: ignore[arg-type]
            access_key_id=settings.R2_ACCESS_KEY_ID,  # type: ignore[arg-type]
            secret_access_key=settings.R2_SECRET_ACCESS_KEY,  # type: ignore[arg-type]
            bucket_name=settings.R2_BUCKET_NAME,  # type: ignore[arg-type]
            endpoint_url=settings.R2_ENDPOINT_URL,
        )

    return LocalStorageProvider(settings.LOCAL_STORAGE_ROOT)
