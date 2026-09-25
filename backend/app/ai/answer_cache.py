"""A small in-process TTL cache for AI Analyst answers — docs/PHASES.md
Phase 8 step 4 ("cache answers keyed by (dataset version, normalized
question)"). Checked what already existed first (per that step's own
instruction): nothing did — every question, even an exact repeat, made
a fresh, full-cost Groq call.

Keyed by (dataset_id, normalized question) rather than a real "dataset
version" field: this app has no dataset-versioning/re-upload-same-id
concept yet (confirmed by reading app/services/dataset_service.py — a
re-upload always creates a new, independent Dataset row with a new id),
so a dataset's content is already immutable for the lifetime of its id.
`dataset_id` alone is therefore already a correct proxy for "version" —
adding a separate version field would track something that can't
currently change.

Deliberately in-process, not Postgres/Redis-backed: this is a single-
process deployment (docs/DEPLOYMENT.md) with no other cross-process
cache today, and adding one is real new infrastructure this step didn't
ask for. Documented limitation, not hidden: this cache does not survive
a process restart and is not shared across multiple worker processes —
correct behavior (a cache miss, not a wrong answer) either way, just
not the maximum possible hit rate. Revisit if this app ever runs with
more than one worker process.
"""
import hashlib
import re
import threading
import time
from typing import Generic, TypeVar
from uuid import UUID

_TTL_SECONDS = 900  # 15 minutes
_MAX_ENTRIES = 500

T = TypeVar("T")

_lock = threading.Lock()
_entries: dict[str, tuple[float, object]] = {}


def _normalize(question: str) -> str:
    return re.sub(r"\s+", " ", question.strip().lower())


def cache_key(dataset_id: UUID, question: str) -> str:
    raw = f"{dataset_id}:{_normalize(question)}"
    return hashlib.sha256(raw.encode()).hexdigest()


class AnswerCache(Generic[T]):
    """Not a singleton by accident — one instance per answer *shape*
    (AnalyzeResponse vs. AskResponse vs. AskSqlResponse) so a cache hit
    can never return the wrong response type to the wrong endpoint."""

    def __init__(self) -> None:
        self._entries = _entries  # process-wide, shared storage
        self._prefix = f"{id(self)}:"

    def get(self, key: str) -> T | None:
        full_key = self._prefix + key
        with _lock:
            entry = self._entries.get(full_key)
            if entry is None:
                return None
            expires_at, value = entry
            if time.monotonic() > expires_at:
                del self._entries[full_key]
                return None
            return value  # type: ignore[return-value]

    def set(self, key: str, value: T) -> None:
        full_key = self._prefix + key
        with _lock:
            if len(self._entries) >= _MAX_ENTRIES and full_key not in self._entries:
                oldest_key = min(self._entries, key=lambda k: self._entries[k][0])
                del self._entries[oldest_key]
            self._entries[full_key] = (time.monotonic() + _TTL_SECONDS, value)

    def clear(self) -> None:
        """Test-only — the module-level store is process-wide and
        otherwise never explicitly cleared."""
        with _lock:
            for key in [k for k in self._entries if k.startswith(self._prefix)]:
                del self._entries[key]
