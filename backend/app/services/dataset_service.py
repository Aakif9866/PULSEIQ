import uuid
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from pathlib import PurePosixPath

from sqlalchemy.orm import Session

from app.analytics.briefing import build_briefing
from app.analytics.loader import load_dataframe
from app.analytics.profiling import profile_dataframe
from app.analytics.query_engine import run_query as _run_query
from app.core.concurrency import submit_in_context
from app.core.config import settings
from app.core.exceptions import (
    DatasetLimitReachedError,
    DatasetNotFoundError,
    DatasetNotReadyError,
    DemoDatasetLockedError,
    FileTooLargeError,
    QueryTimeoutError,
    UnsupportedFileFormatError,
    UnsupportedFileTypeError,
)
from app.core.logging import get_logger
from app.demo import DEMO_FILENAME
from app.models.dataset import Dataset
from app.models.dataset_version import DatasetVersion
from app.models.user import User
from app.repositories.dataset_repository import DatasetRepository
from app.repositories.dataset_version_repository import DatasetVersionRepository
from app.schemas.briefing import DatasetBriefing
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
        self._db = db
        self._repo = DatasetRepository(db)
        self._versions = DatasetVersionRepository(db)
        self._storage = storage

    def ensure_can_upload(self, owner_id: uuid.UUID) -> None:
        """Raises DatasetLimitReachedError at MAX_DATASETS_PER_USER. The
        shared demo account never locks visitors out: its oldest upload
        (never the seeded sample) is dropped to make room instead."""
        if self._repo.count_for_owner(owner_id) < settings.MAX_DATASETS_PER_USER:
            return
        if self._is_demo_owner(owner_id):
            oldest = self._repo.oldest_for_owner(owner_id, exclude_filename=DEMO_FILENAME)
            if oldest is not None:
                self.delete_owned(oldest.id, owner_id)
                return
        raise DatasetLimitReachedError(owner_id)

    def _is_demo_owner(self, owner_id: uuid.UUID) -> bool:
        if not settings.DEMO_USER_EMAIL:
            return False
        user = self._repo.db.get(User, owner_id)
        return user is not None and user.email == settings.DEMO_USER_EMAIL.lower()

    def upload(
        self, *, owner_id: uuid.UUID, filename: str, content_type: str, data: bytes
    ) -> Dataset:
        extension = PurePosixPath(filename).suffix.lower()
        if extension not in settings.ALLOWED_UPLOAD_EXTENSIONS:
            raise UnsupportedFileTypeError(extension)

        self.ensure_can_upload(owner_id)

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
        self._record_version(dataset, previous=None)
        return dataset

    def upload_version(
        self,
        *,
        dataset_id: uuid.UUID,
        owner_id: uuid.UUID,
        filename: str,
        content_type: str,
        data: bytes,
    ) -> tuple[Dataset, DatasetVersion]:
        """Replaces a dataset's data with a new file, keeping the old one on
        record as a previous version. Same limits and profiling as a fresh
        upload; the version row records how the schema changed."""
        dataset = self.get_owned(dataset_id, owner_id)
        if dataset.original_filename == DEMO_FILENAME and self._is_demo_owner(owner_id):
            raise DemoDatasetLockedError(dataset_id)
        extension = PurePosixPath(filename).suffix.lower()
        if extension not in settings.ALLOWED_UPLOAD_EXTENSIONS:
            raise UnsupportedFileTypeError(extension)
        if len(data) > settings.MAX_UPLOAD_SIZE_MB * _BYTES_PER_MB:
            raise FileTooLargeError(len(data))

        previous = self._versions.list_for_dataset(dataset.id)
        previous_version = previous[0] if previous else None
        storage_key = f"{owner_id}/{uuid.uuid4()}{extension}"
        self._storage.save(storage_key, data)
        try:
            dataset.original_filename = filename
            dataset.content_type = content_type
            dataset.size_bytes = len(data)
            dataset.storage_key = storage_key
            dataset.version = dataset.version + 1
            dataset.status = "uploaded"
            self._db.commit()
            self._db.refresh(dataset)
        except Exception:
            self._db.rollback()
            self._storage.delete(storage_key)
            raise
        logger.info("dataset_version_uploaded", dataset_id=str(dataset.id), version=dataset.version)

        self._profile(dataset)
        version = self._record_version(dataset, previous=previous_version)
        self._prune_old_files(dataset)
        return dataset, version

    def list_versions(self, dataset_id: uuid.UUID, owner_id: uuid.UUID) -> list[DatasetVersion]:
        dataset = self.get_owned(dataset_id, owner_id)
        return self._versions.list_for_dataset(dataset.id)

    def _record_version(
        self, dataset: Dataset, *, previous: DatasetVersion | None
    ) -> DatasetVersion:
        columns = [
            {"name": c["name"], "dtype": c["dtype"]} for c in dataset.columns_profile or []
        ]
        return self._versions.create(
            dataset_id=dataset.id,
            version=dataset.version,
            original_filename=dataset.original_filename,
            size_bytes=dataset.size_bytes,
            storage_key=dataset.storage_key,
            row_count=dataset.row_count,
            column_count=dataset.column_count,
            columns=columns or None,
            schema_changes=_schema_changes(previous, columns, dataset.row_count),
        )

    def _prune_old_files(self, dataset: Dataset) -> None:
        """History rows are kept; files beyond MAX_DATASET_VERSIONS_KEPT
        (never the current one) are deleted, so storage stays bounded."""
        kept = 0
        for row in self._versions.list_for_dataset(dataset.id):
            if row.storage_key is None:
                continue
            kept += 1
            if kept <= settings.MAX_DATASET_VERSIONS_KEPT or row.storage_key == dataset.storage_key:
                continue
            try:
                self._storage.delete(row.storage_key)
                self._versions.clear_file(row)
            except Exception:
                logger.error(
                    "dataset_version_prune_failed", dataset_id=str(dataset.id), exc_info=True
                )

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
                duplicate_row_count=profile.duplicate_row_count,
                data_quality_score=profile.data_quality_score,
                correlations=profile.correlations,
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
        old_keys = {
            v.storage_key for v in self._versions.list_for_dataset(dataset.id) if v.storage_key
        } - {storage_key}
        self._repo.delete(dataset)
        for key in [storage_key, *sorted(old_keys)]:
            try:
                self._storage.delete(key)
            except Exception:
                logger.error(
                    "dataset_deleted_but_storage_cleanup_failed",
                    dataset_id=str(dataset_id),
                    storage_key=key,
                    exc_info=True,
                )

    def briefing(self, dataset_id: uuid.UUID, owner_id: uuid.UUID) -> DatasetBriefing:
        """Deterministic overview of a dataset (app/analytics/briefing.py),
        bounded by the same executor and timeout as any other query."""
        dataset = self.get_owned(dataset_id, owner_id)
        if dataset.status != "profiled":
            raise DatasetNotReadyError(dataset.status)
        df = load_dataframe(self._storage, dataset)
        future = submit_in_context(
            _QUERY_EXECUTOR,
            build_briefing,
            df,
            columns_profile=dataset.columns_profile,
            correlations=dataset.correlations,
            duplicate_row_count=dataset.duplicate_row_count,
            data_quality_score=dataset.data_quality_score,
        )
        try:
            return DatasetBriefing.model_validate(
                future.result(timeout=settings.QUERY_TIMEOUT_SECONDS)
            )
        except FutureTimeoutError as exc:
            raise QueryTimeoutError(str(dataset_id)) from exc

    def run_query(
        self, dataset_id: uuid.UUID, owner_id: uuid.UUID, request: DatasetQueryRequest
    ) -> DatasetQueryResult:
        dataset = self.get_owned(dataset_id, owner_id)
        if dataset.status != "profiled":
            raise DatasetNotReadyError(dataset.status)

        df = load_dataframe(self._storage, dataset)
        future = submit_in_context(
            _QUERY_EXECUTOR, _run_query, df, request, row_limit=settings.QUERY_ROW_LIMIT
        )
        try:
            return future.result(timeout=settings.QUERY_TIMEOUT_SECONDS)
        except FutureTimeoutError as exc:
            raise QueryTimeoutError(str(dataset_id)) from exc


def _schema_changes(
    previous: DatasetVersion | None, columns: list[dict[str, str]], row_count: int | None
) -> dict | None:
    """How a new version's columns differ from the previous version's."""
    if previous is None:
        return None
    before = {c["name"]: c["dtype"] for c in previous.columns or []}
    after = {c["name"]: c["dtype"] for c in columns}
    return {
        "previous_version": previous.version,
        "added": [n for n in after if n not in before],
        "removed": [n for n in before if n not in after],
        "type_changed": [
            {"column": n, "from": before[n], "to": after[n]}
            for n in after
            if n in before and before[n] != after[n]
        ],
        "row_count_change": (
            row_count - previous.row_count
            if row_count is not None and previous.row_count is not None
            else None
        ),
    }
