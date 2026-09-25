import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.usage import AiUsageLog


@dataclass
class UsageWindowTotals:
    requests: int
    cache_hits: int
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    # None when no row in the window had a cost (pricing unconfigured) —
    # never a misleading 0.00 for "we don't know".
    estimated_cost_usd: Decimal | None


class UsageRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def create(
        self,
        *,
        owner_id: uuid.UUID,
        dataset_id: uuid.UUID | None,
        source: str,
        status: str,
        cache_hit: bool,
        llm_calls: int,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
        latency_ms: int,
        estimated_cost_usd: float | None,
    ) -> AiUsageLog:
        entry = AiUsageLog(
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
            estimated_cost_usd=(
                Decimal(str(estimated_cost_usd)) if estimated_cost_usd is not None else None
            ),
        )
        self._db.add(entry)
        self._db.commit()
        self._db.refresh(entry)
        return entry

    def totals_since(self, owner_id: uuid.UUID, since: datetime) -> UsageWindowTotals:
        stmt = select(
            func.count(AiUsageLog.id),
            func.count(AiUsageLog.id).filter(AiUsageLog.cache_hit.is_(True)),
            func.coalesce(func.sum(AiUsageLog.prompt_tokens), 0),
            func.coalesce(func.sum(AiUsageLog.completion_tokens), 0),
            func.coalesce(func.sum(AiUsageLog.total_tokens), 0),
            func.sum(AiUsageLog.estimated_cost_usd),
        ).where(AiUsageLog.owner_id == owner_id, AiUsageLog.created_at >= since)
        requests, cache_hits, prompt, completion, total, cost = self._db.execute(stmt).one()
        return UsageWindowTotals(
            requests=int(requests),
            cache_hits=int(cache_hits),
            prompt_tokens=int(prompt),
            completion_tokens=int(completion),
            total_tokens=int(total),
            estimated_cost_usd=cost,
        )
