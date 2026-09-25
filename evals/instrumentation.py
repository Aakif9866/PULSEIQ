"""External token/latency instrumentation for the eval runner — no
production code is touched. app.ai.groq_client.get_groq_client() is an
@lru_cache'd singleton every AI code path in this app goes through
(GroqProvider.chat() for /analyze, app.ai.analyst._chat_completion for
the legacy /ask, app.ai.sql_generator for NL-to-SQL) — patching that one
shared client's chat.completions.create once, here, captures usage for
every path the eval exercises without needing a different mechanism per
path or any change to app/.
"""
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

_BACKEND = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(_BACKEND))

from app.ai.groq_client import get_groq_client  # noqa: E402

_patched = False
_current: "UsageTracker | None" = None


@dataclass
class UsageTracker:
    calls: list[dict] = field(default_factory=list)

    @property
    def call_count(self) -> int:
        return len(self.calls)

    @property
    def total_tokens(self) -> int:
        return sum(c.get("total_tokens", 0) for c in self.calls)

    @property
    def wall_clock_ms(self) -> float:
        return sum(c["latency_ms"] for c in self.calls)

    @property
    def groq_reported_ms(self) -> float:
        return sum(c.get("total_time_ms", 0) for c in self.calls)


def _ensure_patched() -> None:
    global _patched
    if _patched:
        return
    client = get_groq_client()
    original_create = client.chat.completions.create

    def _instrumented_create(*args, **kwargs):
        start = time.perf_counter()
        response = original_create(*args, **kwargs)
        latency_ms = (time.perf_counter() - start) * 1000
        if _current is not None:
            usage = getattr(response, "usage", None)
            record = {"latency_ms": latency_ms}
            if usage is not None:
                for attr in ("prompt_tokens", "completion_tokens", "total_tokens"):
                    value = getattr(usage, attr, None)
                    if value is not None:
                        record[attr] = value
                total_time = getattr(usage, "total_time", None)
                if total_time is not None:
                    record["total_time_ms"] = total_time * 1000
            _current.calls.append(record)
        return response

    client.chat.completions.create = _instrumented_create
    _patched = True


@contextmanager
def track_usage():
    """Every real Groq call made anywhere during this block — regardless
    of which AI code path makes it — is recorded onto the returned
    UsageTracker."""
    global _current
    _ensure_patched()
    tracker = UsageTracker()
    previous, _current = _current, tracker
    try:
        yield tracker
    finally:
        _current = previous
