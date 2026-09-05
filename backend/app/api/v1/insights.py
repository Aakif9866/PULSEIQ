import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.exceptions import DatasetNotFoundError, InsightNotFoundError
from app.models.user import User
from app.schemas.insight import InsightCreate, InsightRead
from app.services.insight_service import InsightService

router = APIRouter(prefix="/insights", tags=["insights"])


@router.post("", response_model=InsightRead, status_code=status.HTTP_201_CREATED)
def save_insight(
    payload: InsightCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> InsightRead:
    try:
        return InsightService(db).save(current_user.id, payload)
    except DatasetNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found"
        ) from exc


@router.get("", response_model=list[InsightRead])
def list_insights(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[InsightRead]:
    return InsightService(db).list_for_owner(current_user.id)


@router.delete("/{insight_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_insight(
    insight_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    try:
        InsightService(db).delete_owned(insight_id, current_user.id)
    except InsightNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Insight not found"
        ) from exc
