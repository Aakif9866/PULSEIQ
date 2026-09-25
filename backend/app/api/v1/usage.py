from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.usage import UsageSummary
from app.services.usage_service import UsageService

router = APIRouter(prefix="/usage", tags=["usage"])


@router.get("/me", response_model=UsageSummary)
def my_usage(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UsageSummary:
    """The current user's own AI usage for today (UTC). Deliberately
    per-user only — there's no admin/role concept in this app yet, so an
    all-users admin view would need one first rather than exposing every
    user's usage to every user."""
    return UsageService(db).summary(current_user.id)
