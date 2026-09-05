import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.exceptions import ChartNotFoundError, DashboardNotFoundError, DatasetNotFoundError
from app.models.user import User
from app.schemas.dashboard import (
    DashboardChartCreate,
    DashboardChartRead,
    DashboardCreate,
    DashboardDetail,
    DashboardRead,
    MoveChartRequest,
)
from app.services.dashboard_service import DashboardService

router = APIRouter(prefix="/dashboards", tags=["dashboards"])


@router.post("", response_model=DashboardRead, status_code=status.HTTP_201_CREATED)
def create_dashboard(
    payload: DashboardCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DashboardRead:
    return DashboardService(db).create(current_user.id, payload.name)


@router.get("", response_model=list[DashboardRead])
def list_dashboards(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[DashboardRead]:
    return DashboardService(db).list_for_owner(current_user.id)


@router.get("/{dashboard_id}", response_model=DashboardDetail)
def get_dashboard(
    dashboard_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DashboardDetail:
    try:
        return DashboardService(db).get_detail(dashboard_id, current_user.id)
    except DashboardNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Dashboard not found"
        ) from exc


@router.delete("/{dashboard_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_dashboard(
    dashboard_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    try:
        DashboardService(db).delete(dashboard_id, current_user.id)
    except DashboardNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Dashboard not found"
        ) from exc


@router.post(
    "/{dashboard_id}/charts", response_model=DashboardChartRead, status_code=status.HTTP_201_CREATED
)
def add_chart(
    dashboard_id: uuid.UUID,
    payload: DashboardChartCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DashboardChartRead:
    try:
        return DashboardService(db).add_chart(dashboard_id, current_user.id, payload)
    except DashboardNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Dashboard not found"
        ) from exc
    except DatasetNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found"
        ) from exc


@router.delete("/{dashboard_id}/charts/{chart_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_chart(
    dashboard_id: uuid.UUID,
    chart_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    try:
        DashboardService(db).delete_chart(dashboard_id, current_user.id, chart_id)
    except DashboardNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Dashboard not found"
        ) from exc
    except ChartNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Chart not found"
        ) from exc


@router.post("/{dashboard_id}/charts/{chart_id}/move", status_code=status.HTTP_204_NO_CONTENT)
def move_chart(
    dashboard_id: uuid.UUID,
    chart_id: uuid.UUID,
    payload: MoveChartRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    try:
        DashboardService(db).move_chart(dashboard_id, current_user.id, chart_id, payload.direction)
    except DashboardNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Dashboard not found"
        ) from exc
    except ChartNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Chart not found"
        ) from exc
