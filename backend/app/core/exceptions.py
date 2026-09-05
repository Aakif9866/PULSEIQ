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


class InsightNotFoundError(DomainError):
    pass


class DashboardNotFoundError(DomainError):
    pass


class ChartNotFoundError(DomainError):
    pass
