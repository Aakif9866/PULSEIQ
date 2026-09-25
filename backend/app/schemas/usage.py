from datetime import datetime

from pydantic import BaseModel


class UsageSummary(BaseModel):
    """The current user's AI usage for today (UTC) — GET /usage/me."""

    day_start: datetime
    resets_at: datetime
    requests: int
    cache_hits: int
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    # None when per-token pricing isn't configured — "unknown", never a
    # made-up 0.00. See cost_tracking_configured.
    estimated_cost_usd: float | None
    # None when no quota is configured (AI_DAILY_TOKEN_QUOTA_PER_USER).
    quota_tokens: int | None
    remaining_tokens: int | None
    cost_tracking_configured: bool
