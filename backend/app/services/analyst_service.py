import uuid

from sqlalchemy.orm import Session

from app.ai.analyst import build_query_from_question, summarize_result
from app.core.config import settings
from app.core.exceptions import AiNotConfiguredError, DatasetNotReadyError
from app.schemas.ai import AskResponse
from app.services.dataset_service import DatasetService
from app.storage.base import StorageProvider


class AnalystService:
    def __init__(self, db: Session, storage: StorageProvider) -> None:
        self._datasets = DatasetService(db, storage)

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

        return AskResponse(question=question, answer=answer, query=query, result=result)
