import uuid
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError

from sqlalchemy.orm import Session

from app.analytics.loader import load_dataframe
from app.analytics.sql_engine import execute_sql
from app.analytics.sql_validator import validate_and_prepare
from app.analytics.suggested_queries import build_suggested_queries
from app.core.concurrency import submit_in_context
from app.core.config import settings
from app.core.exceptions import (
    DatasetNotFoundError,
    DatasetNotReadyError,
    QueryTimeoutError,
    SavedQueryNotFoundError,
)
from app.models.dataset import Dataset
from app.models.history import QueryHistory
from app.repositories.dataset_repository import DatasetRepository
from app.repositories.query_history_repository import QueryHistoryRepository
from app.repositories.saved_query_repository import SavedQueryRepository
from app.schemas.dataset_query import DatasetQueryResult
from app.schemas.history import (
    QueryHistoryRead,
    RunSqlResponse,
    SavedQueryCreate,
    SavedQueryRead,
    SuggestedQuery,
)
from app.storage.base import StorageProvider

_SQL_EXECUTOR = ThreadPoolExecutor(max_workers=4)


class HistoryService:
    """SQL Explorer execution (a direct, no-AI sibling of the Natural
    Language to SQL path — same validate/execute pipeline, different
    entrypoint), plus query history and saved queries. See
    docs/V2_ROADMAP.md's "SQL Explorer" and "Query and Insight History"
    sections."""

    def __init__(self, db: Session, storage: StorageProvider) -> None:
        self._db = db
        self._storage = storage
        self._datasets = DatasetRepository(db)
        self._history = QueryHistoryRepository(db)
        self._saved = SavedQueryRepository(db)

    def run_sql(self, dataset_id: uuid.UUID, owner_id: uuid.UUID, sql: str) -> RunSqlResponse:
        dataset = self._get_owned_dataset(dataset_id, owner_id)
        if dataset.status != "profiled":
            raise DatasetNotReadyError(dataset.status)

        df = load_dataframe(self._storage, dataset)
        known_columns = {c["name"] for c in (dataset.columns_profile or [])}
        safe_sql = validate_and_prepare(
            sql,
            table_name="dataset",
            allowed_columns=known_columns,
            row_limit=settings.QUERY_ROW_LIMIT,
        )

        future = submit_in_context(_SQL_EXECUTOR, execute_sql, df, safe_sql)
        try:
            result = future.result(timeout=settings.QUERY_TIMEOUT_SECONDS)
        except FutureTimeoutError as exc:
            raise QueryTimeoutError(safe_sql) from exc

        self._history.create(
            owner_id=owner_id,
            dataset_id=dataset_id,
            question=None,
            sql_text=safe_sql,
            result_meta=_result_meta(result),
            source="sql_explorer",
        )
        return RunSqlResponse(sql=safe_sql, result=result)

    def log_ai_query(
        self,
        *,
        owner_id: uuid.UUID,
        dataset_id: uuid.UUID,
        question: str,
        sql_text: str | None,
        result: DatasetQueryResult,
        source: str,
    ) -> None:
        """Called by AnalystService after a real ask()/ask_with_sql() —
        every AI-answered question is logged, not just explicitly saved
        ones (see docs/V2_ROADMAP.md's "Query and Insight History")."""
        self._history.create(
            owner_id=owner_id,
            dataset_id=dataset_id,
            question=question,
            sql_text=sql_text,
            result_meta=_result_meta(result),
            source=source,
        )

    def list_history(
        self, owner_id: uuid.UUID, *, dataset_id: uuid.UUID | None = None
    ) -> list[QueryHistoryRead]:
        entries = self._history.list_for_owner(owner_id, dataset_id=dataset_id)
        return [_to_history_read(e) for e in entries]

    def suggest_queries(self, dataset_id: uuid.UUID, owner_id: uuid.UUID) -> list[SuggestedQuery]:
        dataset = self._get_owned_dataset(dataset_id, owner_id)
        return build_suggested_queries(dataset.columns_profile or [])

    def create_saved_query(self, owner_id: uuid.UUID, payload: SavedQueryCreate) -> SavedQueryRead:
        self._get_owned_dataset(payload.dataset_id, owner_id)  # 404s if not owned
        saved = self._saved.create(
            owner_id=owner_id,
            dataset_id=payload.dataset_id,
            name=payload.name,
            sql_text=payload.sql_text,
        )
        return SavedQueryRead.model_validate(saved)

    def list_saved_queries(
        self, owner_id: uuid.UUID, *, dataset_id: uuid.UUID | None = None
    ) -> list[SavedQueryRead]:
        return [
            SavedQueryRead.model_validate(q)
            for q in self._saved.list_for_owner(owner_id, dataset_id=dataset_id)
        ]

    def delete_saved_query(self, query_id: uuid.UUID, owner_id: uuid.UUID) -> None:
        query = self._saved.get_owned(query_id, owner_id)
        if query is None:
            raise SavedQueryNotFoundError(query_id)
        self._saved.delete(query)

    def _get_owned_dataset(self, dataset_id: uuid.UUID, owner_id: uuid.UUID) -> Dataset:
        dataset = self._datasets.get_owned(dataset_id, owner_id)
        if dataset is None:
            raise DatasetNotFoundError(dataset_id)
        return dataset


def _result_meta(result: DatasetQueryResult) -> dict[str, object]:
    return {"columns": result.columns, "row_count": result.row_count, "truncated": result.truncated}


def _to_history_read(entry: QueryHistory) -> QueryHistoryRead:
    meta = entry.result_meta or {}
    return QueryHistoryRead(
        id=entry.id,
        dataset_id=entry.dataset_id,
        question=entry.question,
        sql_text=entry.sql_text,
        source=entry.source,  # type: ignore[arg-type]
        row_count=meta.get("row_count", 0),
        columns=meta.get("columns", []),
        truncated=meta.get("truncated", False),
        created_at=entry.created_at,
    )
