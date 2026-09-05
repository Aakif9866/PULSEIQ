import uuid
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from pathlib import PurePosixPath

from sqlalchemy.orm import Session

from app.analytics.loader import load_dataframe
from app.analytics.profiling import profile_dataframe
from app.analytics.query_engine import run_query as _run_query
from app.core.config import settings
from app.core.exceptions import (
    DatasetNotFoundError,
    DatasetNotReadyError,
    FileTooLargeError,
    QueryTimeoutError,
    UnsupportedFileFormatError,
    UnsupportedFileTypeError,
)
from app.core.logging import get_logger
from app.models.dataset import Dataset
from app.repositories.dataset_repository import DatasetRepository
from app.schemas.dataset_query import DatasetQueryRequest, DatasetQueryResult
from app.storage.base import StorageProvider

logger = get_logger(__name__)

_BYTES_PER_MB = 1024 * 1024
# One worker is enough: this bounds query wall-clock time from the caller's
# perspective. It does not forcibly kill the underlying Polars computation
# (Python can't cancel a running native call) — a real cancellation would
# need an out-of-process worker, which is out of scope until Phase 6.
_QUERY_EXECUTOR = ThreadPoolExecutor(max_workers=4)


class DatasetService:
    def __init__(self, db: Session, storage: StorageProvider) -> None:
        self._repo = DatasetRepository(db)
        self._storage = storage

    def upload(
        self, *, owner_id: uuid.UUID, filename: str, content_type: str, data: bytes
    ) -> Dataset:
        extension = PurePosixPath(filename).suffix.lower()
        if extension not in settings.ALLOWED_UPLOAD_EXTENSIONS:
            raise UnsupportedFileTypeError(extension)

        max_bytes = settings.MAX_UPLOAD_SIZE_MB * _BYTES_PER_MB
        if len(data) > max_bytes:
            raise FileTooLargeError(len(data))

        storage_key = f"{owner_id}/{uuid.uuid4()}{extension}"
        self._storage.save(storage_key, data)

        try:
            dataset = self._repo.create(
                owner_id=owner_id,
                original_filename=filename,
                content_type=content_type,
                size_bytes=len(data),
                storage_key=storage_key,
            )
        except Exception:
            # The file is already on disk/R2 but has no DB row to reference
            # it — clean it up rather than leave an orphaned object behind.
            logger.error("dataset_create_failed_cleaning_up_storage", storage_key=storage_key)
            self._storage.delete(storage_key)
            raise

        logger.info("dataset_uploaded", dataset_id=str(dataset.id), owner_id=str(owner_id))

        self._profile(dataset)
        return dataset

    def _profile(self, dataset: Dataset) -> None:
        """Best-effort: the upload has already succeeded and been persisted,
        so a profiling failure degrades the dataset's status rather than
        failing the request."""
        try:
            df = load_dataframe(self._storage, dataset)
            profile = profile_dataframe(df)
            self._repo.mark_profiled(
                dataset,
                row_count=profile.row_count,
                column_count=profile.column_count,
                columns_profile=profile.columns,
            )
            logger.info("dataset_profiled", dataset_id=str(dataset.id), row_count=profile.row_count)
        except UnsupportedFileFormatError as exc:
            logger.warning(
                "dataset_profiling_unsupported", dataset_id=str(dataset.id), extension=str(exc)
            )
            self._repo.mark_profiling_failed(dataset)
        except Exception:
            logger.error("dataset_profiling_failed", dataset_id=str(dataset.id), exc_info=True)
            self._repo.mark_profiling_failed(dataset)

    def get_owned(self, dataset_id: uuid.UUID, owner_id: uuid.UUID) -> Dataset:
        dataset = self._repo.get_owned(dataset_id, owner_id)
        if dataset is None:
            raise DatasetNotFoundError(dataset_id)
        return dataset

    def list_for_owner(self, owner_id: uuid.UUID) -> list[Dataset]:
        return self._repo.list_for_owner(owner_id)

    def delete_owned(self, dataset_id: uuid.UUID, owner_id: uuid.UUID) -> None:
        dataset = self.get_owned(dataset_id, owner_id)
        storage_key = dataset.storage_key

        # DB row goes first: if this fails, nothing changes and the dataset
        # stays fully usable. If it succeeds but the storage delete below
        # fails, the result is an orphaned file with no DB row pointing to
        # it — invisible to the app and harmless beyond wasted disk space.
        # The reverse order risks a live DB row pointing at a file that's
        # already gone, which surfaces as a broken dataset instead.
        self._repo.delete(dataset)
        try:
            self._storage.delete(storage_key)
        except Exception:
            logger.error(
                "dataset_deleted_but_storage_cleanup_failed",
                dataset_id=str(dataset_id),
                storage_key=storage_key,
                exc_info=True,
            )

    def run_query(
        self, dataset_id: uuid.UUID, owner_id: uuid.UUID, request: DatasetQueryRequest
    ) -> DatasetQueryResult:
        dataset = self.get_owned(dataset_id, owner_id)
        if dataset.status != "profiled":
            raise DatasetNotReadyError(dataset.status)

        df = load_dataframe(self._storage, dataset)
        future = _QUERY_EXECUTOR.submit(_run_query, df, request, row_limit=settings.QUERY_ROW_LIMIT)
        try:
            return future.result(timeout=settings.QUERY_TIMEOUT_SECONDS)
        except FutureTimeoutError as exc:
            raise QueryTimeoutError(str(dataset_id)) from exc
