from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.user import User

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check() -> dict[str, str | int]:
    # storage_provider is non-sensitive (just "local"/"r2", never
    # credentials) — exposed so the frontend can show an accurate note
    # about dataset persistence instead of a hardcoded assumption. The
    # upload limits are exposed for the same reason.
    return {
        "status": "ok",
        "storage_provider": settings.STORAGE_PROVIDER,
        "max_upload_size_mb": settings.MAX_UPLOAD_SIZE_MB,
        "max_datasets_per_user": settings.MAX_DATASETS_PER_USER,
    }


@router.get("/stats")
def public_stats(db: Session = Depends(get_db)) -> dict[str, int]:
    """Public, aggregate-only: the landing page's sign-up count."""
    return {"total_users": db.scalar(select(func.count()).select_from(User)) or 0}
