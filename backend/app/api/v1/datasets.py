import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_storage
from app.core.config import settings
from app.core.database import get_db
from app.core.exceptions import (
    ColumnNotFoundError,
    DatasetLimitReachedError,
    DatasetNotFoundError,
    DatasetNotReadyError,
    DemoDatasetLockedError,
    FileTooLargeError,
    InvalidQueryError,
    QueryTimeoutError,
    UnsupportedFileTypeError,
)
from app.core.rate_limit import rate_limit
from app.models.user import User
from app.schemas.briefing import DatasetBriefing
from app.schemas.dataset import DatasetRead, DatasetVersionRead, VersionUploadResult
from app.schemas.dataset_query import DatasetQueryRequest, DatasetQueryResult
from app.services.dataset_service import DatasetService
from app.storage import StorageProvider

_BYTES_PER_MB = 1024 * 1024
_CHUNK_BYTES = 1024 * 1024


async def _read_limited(file: UploadFile, max_bytes: int) -> bytes:
    buffer = bytearray()
    while chunk := await file.read(_CHUNK_BYTES):
        buffer += chunk
        if len(buffer) > max_bytes:
            raise FileTooLargeError(len(buffer))
    return bytes(buffer)


router = APIRouter(prefix="/datasets", tags=["datasets"])


@router.post(
    "",
    response_model=DatasetRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit("upload", 10, 60))],
)
async def upload_dataset(
    file: UploadFile,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    storage: StorageProvider = Depends(get_storage),
) -> DatasetRead:
    service = DatasetService(db, storage)
    try:
        # Both limits are checked before the file is held in memory: the
        # count first, then the size while reading in chunks.
        service.ensure_can_upload(current_user.id)
        data = await _read_limited(file, settings.MAX_UPLOAD_SIZE_MB * _BYTES_PER_MB)
        dataset = service.upload(
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
            detail=f"Upload limit: each file can be at most {settings.MAX_UPLOAD_SIZE_MB} MB.",
        ) from exc
    except DatasetLimitReachedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Upload limit: you can keep up to {settings.MAX_DATASETS_PER_USER} "
            "datasets. Delete one to upload another.",
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


@router.post(
    "/{dataset_id}/versions",
    response_model=VersionUploadResult,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit("upload", 10, 60))],
)
async def upload_dataset_version(
    dataset_id: uuid.UUID,
    file: UploadFile,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    storage: StorageProvider = Depends(get_storage),
) -> VersionUploadResult:
    """Refreshes a dataset with a new file, keeping the old version on
    record, then re-runs the dataset's anomaly checks on the new data."""
    service = DatasetService(db, storage)
    try:
        data = await _read_limited(file, settings.MAX_UPLOAD_SIZE_MB * _BYTES_PER_MB)
        dataset, version = service.upload_version(
            dataset_id=dataset_id,
            owner_id=current_user.id,
            filename=file.filename or "upload",
            content_type=file.content_type or "application/octet-stream",
            data=data,
        )
    except DatasetNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found"
        ) from exc
    except DemoDatasetLockedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The shared demo dataset can't be replaced. Upload your own file instead.",
        ) from exc
    except UnsupportedFileTypeError as exc:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Unsupported file type. Allowed: .csv, .xlsx, .xls",
        ) from exc
    except FileTooLargeError as exc:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Upload limit: each file can be at most {settings.MAX_UPLOAD_SIZE_MB} MB.",
        ) from exc

    checks = []
    if dataset.status == "profiled":
        from app.services.monitor_service import MonitorService

        checks = MonitorService(db, storage).run_for_dataset(dataset.id, current_user.id)
    return VersionUploadResult(
        dataset=DatasetRead.model_validate(dataset),
        version=_version_read(version),
        checks_run=len(checks),
        # A period already reported comes back with an "already recorded"
        # message; only message-less detections are new.
        new_anomalies=sum(
            1 for c in checks if c.status == "ANOMALY_DETECTED" and c.anomaly and not c.message
        ),
    )


@router.get("/{dataset_id}/versions", response_model=list[DatasetVersionRead])
def list_dataset_versions(
    dataset_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    storage: StorageProvider = Depends(get_storage),
) -> list[DatasetVersionRead]:
    try:
        rows = DatasetService(db, storage).list_versions(dataset_id, current_user.id)
    except DatasetNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found"
        ) from exc
    return [_version_read(v) for v in rows]


def _version_read(row) -> DatasetVersionRead:
    return DatasetVersionRead(
        version=row.version,
        original_filename=row.original_filename,
        size_bytes=row.size_bytes,
        row_count=row.row_count,
        column_count=row.column_count,
        schema_changes=row.schema_changes,
        file_kept=row.storage_key is not None,
        created_at=row.created_at,
    )


@router.get(
    "/{dataset_id}/briefing",
    response_model=DatasetBriefing,
    dependencies=[Depends(rate_limit("query", 60, 60))],
)
def dataset_briefing(
    dataset_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    storage: StorageProvider = Depends(get_storage),
) -> DatasetBriefing:
    """Deterministic overview + suggested questions. Costs no AI quota."""
    try:
        return DatasetService(db, storage).briefing(dataset_id, current_user.id)
    except DatasetNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found"
        ) from exc
    except DatasetNotReadyError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This dataset isn't ready yet (profiling hasn't succeeded).",
        ) from exc
    except QueryTimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Building the briefing took too long for this dataset.",
        ) from exc


@router.post(
    "/{dataset_id}/query",
    response_model=DatasetQueryResult,
    dependencies=[Depends(rate_limit("query", 60, 60))],
)
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
