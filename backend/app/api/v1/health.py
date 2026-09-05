from fastapi import APIRouter

from app.core.config import settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check() -> dict[str, str]:
    # storage_provider is non-sensitive (just "local"/"r2", never
    # credentials) — exposed so the frontend can show an accurate note
    # about dataset persistence instead of a hardcoded assumption.
    return {"status": "ok", "storage_provider": settings.STORAGE_PROVIDER}
