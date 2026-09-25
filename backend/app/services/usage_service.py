"""Per-user AI usage: recording, daily token quotas, and the summary the
usage page shows — docs/PHASES.md Phase 8 step 4.

What's counted, stated plainly: token usage is recorded for the hybrid
AI Analyst (`/analyze`, the frontend's default AI path) — the only path
that goes through the AIProvider abstraction, so the only one whose
real token counts are available without rewriting working code (see
app/ai/providers/usage_tracking.py). The deprecated `/ask` and the
NL-to-SQL `/ask-sql` paths call the Groq client directly and don't
report tokens yet. They *are* still blocked once a user is over quota
(enforce_quota runs for all three), so the quota can't be bypassed by
switching endpoints — their own spend just isn't added to the count.
Documented in docs/AI_ANALYTICS.md as a known gap.
"""
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import AiQuotaExceededError
from app.core.logging import get_logger
from app.repositories.usage_repository import UsageRepository
from app.schemas.usage import UsageSummary

logger = get_logger(__name__)


def _now() -> datetime:
    """Its own function so tests can move the clock across a UTC midnight."""
    return datetime.now(UTC)


def _day_window(now: datetime) -> tuple[datetime, datetime]:
    """UTC calendar day, not a rolling 24h window — a fixed, predictable
    reset time ("midnight UTC") is something a user can actually be told;
    a rolling window's reset moment depends on when their earliest
    request in the last 24h happened, which nobody can reason about."""
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return start, start + timedelta(days=1)


class UsageService:
    def __init__(self, db: Session) -> None:
        self._repo = UsageRepository(db)

    def enforce_quota(self, owner_id: uuid.UUID) -> None:
        quota = settings.AI_DAILY_TOKEN_QUOTA_PER_USER
        if quota is None:
            return
        start, resets_at = _day_window(_now())
        used = self._repo.totals_since(owner_id, start).total_tokens
        if used >= quota:
            logger.info("ai_quota_exceeded", owner_id=str(owner_id), used=used, quota=quota)
            raise AiQuotaExceededError(used, quota, resets_at.isoformat())

    def record(
        self,
        *,
        owner_id: uuid.UUID,
        dataset_id: uuid.UUID | None,
        source: str,
        status: str,
        cache_hit: bool,
        llm_calls: int = 0,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        total_tokens: int = 0,
        latency_ms: int = 0,
        estimated_cost_usd: float | None = None,
    ) -> None:
        """Best-effort: a failure to record usage must never turn an
        already-computed, correct answer into an error for the user."""
        try:
            self._repo.create(
                owner_id=owner_id,
                dataset_id=dataset_id,
                source=source,
                status=status,
                cache_hit=cache_hit,
                llm_calls=llm_calls,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                latency_ms=latency_ms,
                estimated_cost_usd=estimated_cost_usd,
            )
        except Exception:  # noqa: BLE001 - usage logging must never break a response
            logger.exception("ai_usage_record_failed", owner_id=str(owner_id))

    def summary(self, owner_id: uuid.UUID) -> UsageSummary:
        start, resets_at = _day_window(_now())
        totals = self._repo.totals_since(owner_id, start)
        quota = settings.AI_DAILY_TOKEN_QUOTA_PER_USER
        return UsageSummary(
            day_start=start,
            resets_at=resets_at,
            requests=totals.requests,
            cache_hits=totals.cache_hits,
            prompt_tokens=totals.prompt_tokens,
            completion_tokens=totals.completion_tokens,
            total_tokens=totals.total_tokens,
            estimated_cost_usd=(
                float(totals.estimated_cost_usd)
                if totals.estimated_cost_usd is not None
                else None
            ),
            quota_tokens=quota,
            remaining_tokens=max(quota - totals.total_tokens, 0) if quota is not None else None,
            cost_tracking_configured=(
                settings.GROQ_INPUT_COST_PER_1M_TOKENS is not None
                and settings.GROQ_OUTPUT_COST_PER_1M_TOKENS is not None
            ),
        )
