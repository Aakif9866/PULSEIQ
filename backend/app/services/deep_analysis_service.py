import uuid

from sqlalchemy.orm import Session

from app.ai.analyst_engine import run_analysis
from app.ai.providers.groq_provider import GroqProvider
from app.analytics.loader import load_dataframe
from app.core.config import settings
from app.core.exceptions import AiNotConfiguredError, DatasetNotReadyError
from app.repositories.dataset_repository import DatasetRepository
from app.repositories.query_history_repository import QueryHistoryRepository
from app.schemas.analysis import AnalyzeRequest, AnalyzeResponse
from app.services.dataset_service import DatasetService
from app.storage.base import StorageProvider


class DeepAnalysisService:
    """The hybrid AI Analyst (docs/AI_ANALYTICS.md) — a sibling to
    AnalystService.ask()/ask_with_sql(), not a replacement for them. Those
    two remain single-shot (one structured query or one SQL query, then
    summarize); this one runs a full tool-calling loop against the FULL
    dataset for open-ended, possibly multi-step analytical questions."""

    def __init__(self, db: Session, storage: StorageProvider) -> None:
        self._db = db
        self._storage = storage
        self._datasets = DatasetService(db, storage)
        self._dataset_repo = DatasetRepository(db)
        self._history = QueryHistoryRepository(db)

    def analyze(
        self, dataset_id: uuid.UUID, owner_id: uuid.UUID, payload: AnalyzeRequest
    ) -> AnalyzeResponse:
        if settings.AI_PROVIDER != "groq":
            raise AiNotConfiguredError()

        dataset = self._datasets.get_owned(dataset_id, owner_id)
        if dataset.status != "profiled":
            raise DatasetNotReadyError(dataset.status)

        df = load_dataframe(self._storage, dataset)
        response = run_analysis(
            df, GroqProvider(), payload.question, payload.conversation_history
        )

        # Best-effort logging — a history-write failure must never affect
        # an already-computed analysis result.
        try:
            self._history.create(
                owner_id=owner_id,
                dataset_id=dataset_id,
                question=payload.question,
                sql_text=None,
                result_meta={
                    "tool_calls": [tc.tool for tc in response.tool_calls],
                    "findings_count": len(response.findings),
                    "status": response.status,
                },
                source="ai_deep_analysis",
            )
        except Exception:  # noqa: BLE001 - logging must never break the response
            pass

        return response
