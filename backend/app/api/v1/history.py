import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_storage
from app.core.database import get_db
from app.core.exceptions import (
    DatasetNotFoundError,
    DatasetNotReadyError,
    InvalidQueryError,
    QueryTimeoutError,
    SavedQueryNotFoundError,
)
from app.models.user import User
from app.schemas.history import (
    QueryHistoryRead,
    RunSqlRequest,
    RunSqlResponse,
    SavedQueryCreate,
    SavedQueryRead,
    SuggestedQuery,
)
from app.services.history_service import HistoryService
from app.storage import StorageProvider

router = APIRouter(tags=["sql-explorer"])


def _not_found(detail: str):
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


@router.post("/datasets/{dataset_id}/sql", response_model=RunSqlResponse)
def run_sql(
    dataset_id: uuid.UUID,
    payload: RunSqlRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    storage: StorageProvider = Depends(get_storage),
) -> RunSqlResponse:
    """The SQL Explorer's "Run query" — a direct, no-AI sibling of
    /ask-sql. Same validation + DuckDB execution pipeline."""
    try:
        return HistoryService(db, storage).run_sql(dataset_id, current_user.id, payload.sql)
    except DatasetNotFoundError as exc:
        raise _not_found("Dataset not found") from exc
    except DatasetNotReadyError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This dataset isn't ready to query yet (profiling hasn't succeeded).",
        ) from exc
    except InvalidQueryError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    except QueryTimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_408_REQUEST_TIMEOUT,
            detail="That query took too long to run. Try narrowing it down.",
        ) from exc


@router.get("/datasets/{dataset_id}/suggested-queries", response_model=list[SuggestedQuery])
def suggested_queries(
    dataset_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    storage: StorageProvider = Depends(get_storage),
) -> list[SuggestedQuery]:
    try:
        return HistoryService(db, storage).suggest_queries(dataset_id, current_user.id)
    except DatasetNotFoundError as exc:
        raise _not_found("Dataset not found") from exc


@router.get("/history", response_model=list[QueryHistoryRead])
def list_history(
    dataset_id: uuid.UUID | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    storage: StorageProvider = Depends(get_storage),
) -> list[QueryHistoryRead]:
    return HistoryService(db, storage).list_history(current_user.id, dataset_id=dataset_id)


@router.post("/queries", response_model=SavedQueryRead, status_code=status.HTTP_201_CREATED)
def create_saved_query(
    payload: SavedQueryCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    storage: StorageProvider = Depends(get_storage),
) -> SavedQueryRead:
    try:
        return HistoryService(db, storage).create_saved_query(current_user.id, payload)
    except DatasetNotFoundError as exc:
        raise _not_found("Dataset not found") from exc


@router.get("/queries", response_model=list[SavedQueryRead])
def list_saved_queries(
    dataset_id: uuid.UUID | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    storage: StorageProvider = Depends(get_storage),
) -> list[SavedQueryRead]:
    return HistoryService(db, storage).list_saved_queries(current_user.id, dataset_id=dataset_id)


@router.delete("/queries/{query_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_saved_query(
    query_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    storage: StorageProvider = Depends(get_storage),
) -> None:
    try:
        HistoryService(db, storage).delete_saved_query(query_id, current_user.id)
    except SavedQueryNotFoundError as exc:
        raise _not_found("Saved query not found") from exc
