import uuid
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError

from sqlalchemy.orm import Session

from app.ai.analyst import build_query_from_question, summarize_result
from app.ai.sql_generator import build_sql_from_question
from app.analytics.chart_suggestion import suggest_chart_type
from app.analytics.loader import load_dataframe
from app.analytics.sql_engine import execute_sql
from app.analytics.sql_validator import validate_and_prepare
from app.core.config import settings
from app.core.exceptions import AiNotConfiguredError, DatasetNotReadyError, QueryTimeoutError
from app.schemas.ai import AskResponse, AskSqlResponse
from app.schemas.dataset_query import DatasetQueryResult
from app.services.dataset_service import DatasetService
from app.services.history_service import HistoryService
from app.storage.base import StorageProvider

# Bounds SQL execution wall-clock time the same way DatasetService bounds
# structured-query execution — one worker is enough, this only limits how
# long a caller waits, not the underlying DuckDB call itself.
_SQL_EXECUTOR = ThreadPoolExecutor(max_workers=4)


class AnalystService:
    def __init__(self, db: Session, storage: StorageProvider) -> None:
        self._datasets = DatasetService(db, storage)
        self._storage = storage
        self._history = HistoryService(db, storage)

    def ask(self, dataset_id: uuid.UUID, owner_id: uuid.UUID, question: str) -> AskResponse:
        if settings.AI_PROVIDER != "groq":
            raise AiNotConfiguredError()

        # get_owned raises DatasetNotFoundError if missing/not owned.
        dataset = self._datasets.get_owned(dataset_id, owner_id)
        if dataset.status != "profiled":
            raise DatasetNotReadyError(dataset.status)

        query = build_query_from_question(question, dataset)
        # Re-checks ownership/status and enforces QUERY_ROW_LIMIT/QUERY_TIMEOUT_SECONDS
        # exactly as a hand-built query would.
        result = self._datasets.run_query(dataset_id, owner_id, query)
        answer = summarize_result(question, result)

        self._history.log_ai_query(
            owner_id=owner_id,
            dataset_id=dataset_id,
            question=question,
            sql_text=None,  # a structured query, not SQL text
            result=result,
            source="ai_structured",
        )
        dtypes = {c["name"]: c["dtype"] for c in (dataset.columns_profile or [])}
        return AskResponse(
            question=question,
            answer=answer,
            query=query,
            result=result,
            suggested_chart_type=suggest_chart_type(query, dtypes),
        )

    def ask_with_sql(
        self, dataset_id: uuid.UUID, owner_id: uuid.UUID, question: str
    ) -> AskSqlResponse:
        """The Natural Language to SQL path (docs/V2_ROADMAP.md) — a
        second, independent way to answer a question, alongside ask()
        above. Reuses summarize_result() unchanged: it only cares that it
        received a real DatasetQueryResult, not how it was computed."""
        if settings.AI_PROVIDER != "groq":
            raise AiNotConfiguredError()

        dataset = self._datasets.get_owned(dataset_id, owner_id)
        if dataset.status != "profiled":
            raise DatasetNotReadyError(dataset.status)

        df = load_dataframe(self._storage, dataset)
        raw_sql = build_sql_from_question(question, dataset, df)

        known_columns = {c["name"] for c in (dataset.columns_profile or [])}
        safe_sql = validate_and_prepare(
            raw_sql,
            table_name="dataset",
            allowed_columns=known_columns,
            row_limit=settings.QUERY_ROW_LIMIT,
        )

        result = self._run_sql_bounded(df, safe_sql)
        answer = summarize_result(question, result)

        self._history.log_ai_query(
            owner_id=owner_id,
            dataset_id=dataset_id,
            question=question,
            sql_text=safe_sql,
            result=result,
            source="ai_sql",
        )
        return AskSqlResponse(
            question=question, answer=answer, generated_sql=safe_sql, result=result
        )

    def _run_sql_bounded(self, df, sql: str) -> DatasetQueryResult:
        future = _SQL_EXECUTOR.submit(execute_sql, df, sql)
        try:
            return future.result(timeout=settings.QUERY_TIMEOUT_SECONDS)
        except FutureTimeoutError as exc:
            raise QueryTimeoutError(sql) from exc
