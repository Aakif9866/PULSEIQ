import uuid

from sqlalchemy.orm import Session

from app.ai.analyst_engine import run_analysis
from app.ai.answer_cache import AnswerCache, cache_key
from app.ai.providers.groq_provider import GroqProvider
from app.ai.providers.usage_tracking import UsageTrackingProvider
from app.analytics.loader import load_dataframe
from app.core.config import settings
from app.core.exceptions import AiNotConfiguredError, DatasetNotReadyError
from app.core.logging import get_logger
from app.repositories.dataset_repository import DatasetRepository
from app.repositories.query_history_repository import QueryHistoryRepository
from app.schemas.analysis import AnalyzeRequest, AnalyzeResponse
from app.services.dataset_service import DatasetService
from app.services.usage_service import UsageService
from app.storage.base import StorageProvider

logger = get_logger(__name__)

_USAGE_SOURCE = "ai_deep_analysis"

# Module-level (not per-request) — see app/ai/answer_cache.py: this is
# what makes it an actual cache rather than a new empty dict every call.
_answer_cache: AnswerCache[AnalyzeResponse] = AnswerCache()


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
        self._usage = UsageService(db)

    def analyze(
        self, dataset_id: uuid.UUID, owner_id: uuid.UUID, payload: AnalyzeRequest
    ) -> AnalyzeResponse:
        if settings.AI_PROVIDER != "groq":
            raise AiNotConfiguredError()

        dataset = self._datasets.get_owned(dataset_id, owner_id)
        if dataset.status != "profiled":
            raise DatasetNotReadyError(dataset.status)

        # Only a fresh, standalone question is cacheable — one asked as
        # part of a follow-up (conversation_history non-empty) depends on
        # that context, so the same question text can mean something
        # different and must never be served from an earlier, context-
        # free answer.
        cacheable = not payload.conversation_history
        key = cache_key(dataset_id, payload.question) if cacheable else None
        if key is not None:
            cached = _answer_cache.get(key)
            if cached is not None:
                logger.info("analyze_cache_hit", dataset_id=str(dataset_id))
                # A cache hit costs no tokens, so it's served even to a
                # user who's over quota — and recorded with 0 tokens so the
                # usage page can show how many answers came from cache.
                self._usage.record(
                    owner_id=owner_id, dataset_id=dataset_id, source=_USAGE_SOURCE,
                    status=cached.status, cache_hit=True,
                )
                return cached

        # Checked only now — after the free cache path, before anything
        # that actually spends tokens.
        self._usage.enforce_quota(owner_id)

        df = load_dataframe(self._storage, dataset)
        provider = UsageTrackingProvider(GroqProvider())
        response = run_analysis(df, provider, payload.question, payload.conversation_history)

        logger.info(
            "analyze_request_completed",
            dataset_id=str(dataset_id),
            status=response.status,
            tool_calls=len(response.tool_calls),
            llm_calls=provider.totals.call_count,
            prompt_tokens=provider.totals.prompt_tokens,
            completion_tokens=provider.totals.completion_tokens,
            total_tokens=provider.totals.total_tokens,
            latency_ms=round(provider.totals.wall_clock_ms),
            estimated_cost_usd=provider.totals.estimated_cost_usd,
            cache_hit=False,
        )
        self._usage.record(
            owner_id=owner_id,
            dataset_id=dataset_id,
            source=_USAGE_SOURCE,
            status=response.status,
            cache_hit=False,
            llm_calls=provider.totals.call_count,
            prompt_tokens=provider.totals.prompt_tokens,
            completion_tokens=provider.totals.completion_tokens,
            total_tokens=provider.totals.total_tokens,
            latency_ms=round(provider.totals.wall_clock_ms),
            estimated_cost_usd=provider.totals.estimated_cost_usd,
        )

        # Only a genuinely "ok" answer is worth caching — a degraded
        # fallback response should get a real retry next time, not the
        # same fallback message served back for 15 more minutes.
        if key is not None and response.status == "ok":
            _answer_cache.set(key, response)

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
