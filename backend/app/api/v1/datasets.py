import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_storage
from app.core.database import get_db
from app.core.exceptions import (
    ColumnNotFoundError,
    DatasetNotFoundError,
    DatasetNotReadyError,
    FileTooLargeError,
    InvalidQueryError,
    QueryTimeoutError,
    UnsupportedFileTypeError,
)
from app.models.user import User
from app.schemas.dataset import DatasetRead
from app.schemas.dataset_query import DatasetQueryRequest, DatasetQueryResult
from app.services.dataset_service import DatasetService
from app.storage import StorageProvider

router = APIRouter(prefix="/datasets", tags=["datasets"])


@router.post("", response_model=DatasetRead, status_code=status.HTTP_201_CREATED)
async def upload_dataset(
    file: UploadFile,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    storage: StorageProvider = Depends(get_storage),
) -> DatasetRead:
    data = await file.read()
    try:
        dataset = DatasetService(db, storage).upload(
            owner_id=current_user.id,
            filename=file.filename or "upload",
            content_type=file.content_type or "application/octet-stream",
            data=data,
        )
    except UnsupportedFileTypeError as exc:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Unsupported file type. Allowed: .csv, .xlsx, .xls",
        ) from exc
    except FileTooLargeError as exc:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File exceeds the maximum upload size.",
        ) from exc

    return DatasetRead.model_validate(dataset)


@router.get("", response_model=list[DatasetRead])
def list_datasets(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    storage: StorageProvider = Depends(get_storage),
) -> list[DatasetRead]:
    datasets = DatasetService(db, storage).list_for_owner(current_user.id)
    return [DatasetRead.model_validate(dataset) for dataset in datasets]


@router.get("/{dataset_id}", response_model=DatasetRead)
def get_dataset(
    dataset_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    storage: StorageProvider = Depends(get_storage),
) -> DatasetRead:
    try:
        dataset = DatasetService(db, storage).get_owned(dataset_id, current_user.id)
    except DatasetNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found"
        ) from exc

    return DatasetRead.model_validate(dataset)


@router.post("/{dataset_id}/query", response_model=DatasetQueryResult)
def query_dataset(
    dataset_id: uuid.UUID,
    payload: DatasetQueryRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    storage: StorageProvider = Depends(get_storage),
) -> DatasetQueryResult:
    try:
        return DatasetService(db, storage).run_query(dataset_id, current_user.id, payload)
    except DatasetNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found"
        ) from exc
    except DatasetNotReadyError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This dataset isn't ready to query yet (profiling hasn't succeeded).",
        ) from exc
    except ColumnNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown column(s): {exc}"
        ) from exc
    except InvalidQueryError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except QueryTimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_408_REQUEST_TIMEOUT,
            detail="The query took too long to run. Try narrowing it down.",
        ) from exc


@router.delete("/{dataset_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_dataset(
    dataset_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    storage: StorageProvider = Depends(get_storage),
) -> None:
    try:
        DatasetService(db, storage).delete_owned(dataset_id, current_user.id)
    except DatasetNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found"
        ) from exc
