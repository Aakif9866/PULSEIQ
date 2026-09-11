import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_storage
from app.core.database import get_db
from app.core.exceptions import (
    ColumnNotFoundError,
    DatasetNotFoundError,
    DatasetNotReadyError,
    MonitorNotFoundError,
)
from app.models.user import User
from app.schemas.monitor import (
    AnomalyRead,
    MonitorCreate,
    MonitorRead,
    MonitorRunResult,
    MonitorUpdate,
)
from app.services.monitor_service import MonitorService
from app.storage import StorageProvider

router = APIRouter(prefix="/monitors", tags=["monitors"])


def _not_found(detail: str):
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


@router.post("", response_model=MonitorRead, status_code=status.HTTP_201_CREATED)
def create_monitor(
    payload: MonitorCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    storage: StorageProvider = Depends(get_storage),
) -> MonitorRead:
    try:
        return MonitorService(db, storage).create(current_user.id, payload)
    except DatasetNotFoundError as exc:
        raise _not_found("Dataset not found") from exc
    except DatasetNotReadyError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This dataset isn't ready to monitor yet (profiling hasn't succeeded).",
        ) from exc
    except ColumnNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Column not found in dataset: {exc}",
        ) from exc


@router.get("", response_model=list[MonitorRead])
def list_monitors(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db),
    storage: StorageProvider = Depends(get_storage),
) -> list[MonitorRead]:
    return MonitorService(db, storage).list_for_owner(current_user.id)


@router.get("/anomalies", response_model=list[AnomalyRead])
def list_anomalies(
    monitor_id: uuid.UUID | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    storage: StorageProvider = Depends(get_storage),
) -> list[AnomalyRead]:
    try:
        return MonitorService(db, storage).list_anomalies(current_user.id, monitor_id=monitor_id)
    except MonitorNotFoundError as exc:
        raise _not_found("Monitor not found") from exc


@router.get("/{monitor_id}", response_model=MonitorRead)
def get_monitor(
    monitor_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    storage: StorageProvider = Depends(get_storage),
) -> MonitorRead:
    try:
        return MonitorService(db, storage).get(monitor_id, current_user.id)
    except MonitorNotFoundError as exc:
        raise _not_found("Monitor not found") from exc


@router.patch("/{monitor_id}", response_model=MonitorRead)
def update_monitor(
    monitor_id: uuid.UUID,
    payload: MonitorUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    storage: StorageProvider = Depends(get_storage),
) -> MonitorRead:
    try:
        return MonitorService(db, storage).update(monitor_id, current_user.id, payload)
    except MonitorNotFoundError as exc:
        raise _not_found("Monitor not found") from exc


@router.delete("/{monitor_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_monitor(
    monitor_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    storage: StorageProvider = Depends(get_storage),
) -> None:
    try:
        MonitorService(db, storage).delete(monitor_id, current_user.id)
    except MonitorNotFoundError as exc:
        raise _not_found("Monitor not found") from exc


@router.post("/{monitor_id}/run", response_model=MonitorRunResult)
def run_monitor(
    monitor_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    storage: StorageProvider = Depends(get_storage),
) -> MonitorRunResult:
    try:
        return MonitorService(db, storage).run_monitor(monitor_id, current_user.id)
    except MonitorNotFoundError as exc:
        raise _not_found("Monitor not found") from exc
