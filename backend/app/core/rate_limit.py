"""Per-client sliding-window rate limits for the abuse-prone routes
(login, signup, refresh, AI, uploads).

# ponytail: in-process memory, correct for a single instance (Render free
# runs one). Running several instances needs a shared store (Redis).
"""
import threading
import time
from collections import deque
from collections.abc import Callable

from fastapi import HTTPException, Request, status

from app.core.config import settings

_lock = threading.Lock()
_hits: dict[tuple[str, str], deque[float]] = {}
_MAX_KEYS = 50_000


def client_ip(request: Request) -> str:
    """The proxy-appended entry of X-Forwarded-For, counted from the right.
    A client can prepend anything it likes, but not the hops the trusted
    proxies (Render's edge) add after it."""
    hops = settings.TRUSTED_PROXY_HOPS
    forwarded = request.headers.get("x-forwarded-for")
    if hops > 0 and forwarded:
        parts = [p.strip() for p in forwarded.split(",") if p.strip()]
        if parts:
            return parts[-min(hops, len(parts))]
    return request.client.host if request.client else "unknown"


def hit(name: str, key: str, limit: int, window_seconds: int) -> None:
    """Counts one attempt for (name, key); raises 429 past `limit` per window."""
    if not settings.RATE_LIMIT_ENABLED:
        return
    now = time.monotonic()
    with _lock:
        if len(_hits) > _MAX_KEYS:
            _hits.clear()  # crude memory bound; only ever loses old windows' counts
        q = _hits.setdefault((name, key), deque())
        while q and q[0] <= now - window_seconds:
            q.popleft()
        if len(q) >= limit:
            retry_after = int(window_seconds - (now - q[0])) + 1
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please wait a moment and try again.",
                headers={"Retry-After": str(retry_after)},
            )
        q.append(now)


def rate_limit(name: str, limit: int, window_seconds: int) -> Callable[[Request], None]:
    """FastAPI dependency: limits a route per client IP."""

    def dependency(request: Request) -> None:
        hit(name, client_ip(request), limit, window_seconds)

    return dependency


def reset() -> None:
    """For tests."""
    with _lock:
        _hits.clear()
