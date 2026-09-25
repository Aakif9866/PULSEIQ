"""Domain-level exceptions, translated to HTTP responses at the API layer.

Keeping these separate from FastAPI's HTTPException lets services stay free
of HTTP concerns.
"""


class DomainError(Exception):
    """Base class for all expected, user-facing domain errors."""


class EmailAlreadyRegisteredError(DomainError):
    pass


class InvalidCredentialsError(DomainError):
    pass


class InactiveUserError(DomainError):
    pass


class UnsupportedFileTypeError(DomainError):
    pass


class FileTooLargeError(DomainError):
    pass


class DatasetNotFoundError(DomainError):
    pass


class DatasetNotReadyError(DomainError):
    """Raised when a query is attempted before profiling has succeeded."""


class UnsupportedFileFormatError(DomainError):
    """Raised when a file's extension is allowed for upload but not (yet)
    understood by the analytics engine (e.g. legacy .xls)."""


class ColumnNotFoundError(DomainError):
    pass


class InvalidQueryError(DomainError):
    pass


class QueryTimeoutError(DomainError):
    pass


class AiNotConfiguredError(DomainError):
    """Raised when AI_PROVIDER=none but an AI Analyst endpoint is called."""


class AiResponseError(DomainError):
    """Raised when the AI provider errors out, times out, or returns
    something we can't turn into a valid query/answer."""


class AiQuotaExceededError(DomainError):
    """Raised when a user has used up their AI_DAILY_TOKEN_QUOTA_PER_USER
    for the current UTC day (docs/PHASES.md Phase 8 step 4)."""

    def __init__(self, used_tokens: int, quota_tokens: int, resets_at: str) -> None:
        super().__init__(
            f"Daily AI usage limit reached ({used_tokens:,} of {quota_tokens:,} tokens). "
            f"Resets at {resets_at}."
        )
        self.used_tokens = used_tokens
        self.quota_tokens = quota_tokens
        self.resets_at = resets_at


class InsightNotFoundError(DomainError):
    pass


class DashboardNotFoundError(DomainError):
    pass


class ChartNotFoundError(DomainError):
    pass


class MonitorNotFoundError(DomainError):
    pass


class AnomalyNotFoundError(DomainError):
    pass


class SavedQueryNotFoundError(DomainError):
    pass
