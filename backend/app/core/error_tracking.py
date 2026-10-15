"""Optional Sentry error tracking — inert unless SENTRY_DSN is set."""
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def configure_error_tracking() -> None:
    if not settings.SENTRY_DSN:
        return
    import sentry_sdk

    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.ENVIRONMENT,
        send_default_pii=False,  # no IPs, cookies, or request bodies
        traces_sample_rate=0.0,  # errors only; tracing is OpenTelemetry's job
    )
    logger.info("error_tracking_enabled")
