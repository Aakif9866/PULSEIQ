import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.exceptions import DatasetNotFoundError, InsightNotFoundError
from app.models.user import User
from app.schemas.insight import InsightCreate, InsightRead, InsightUpdate
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


def _insight_not_found(exc: Exception) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Insight not found")


@router.get("/{insight_id}", response_model=InsightRead)
def get_insight(
    insight_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> InsightRead:
    try:
        return InsightService(db).get_owned(insight_id, current_user.id)
    except InsightNotFoundError as exc:
        raise _insight_not_found(exc) from exc


@router.patch("/{insight_id}", response_model=InsightRead)
def rename_insight(
    insight_id: uuid.UUID,
    payload: InsightUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> InsightRead:
    try:
        return InsightService(db).rename(insight_id, current_user.id, payload)
    except InsightNotFoundError as exc:
        raise _insight_not_found(exc) from exc


@router.get("/{insight_id}/report", response_class=HTMLResponse)
def insight_report(
    insight_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """A standalone HTML report (prints cleanly to PDF), downloaded as a file."""
    try:
        html, filename = InsightService(db).report_html(insight_id, current_user.id)
    except (InsightNotFoundError, DatasetNotFoundError) as exc:
        raise _insight_not_found(exc) from exc
    return HTMLResponse(
        html,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            # The report embeds the user's own data: never cache it shared.
            "Cache-Control": "private, no-store",
        },
    )


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
