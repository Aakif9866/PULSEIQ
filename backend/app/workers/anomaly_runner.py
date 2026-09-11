"""CLI entrypoint for periodic anomaly-monitor evaluation.

PulseIQ has no background-worker process or task queue (see
docs/V2_ARCHITECTURE.md — deliberately: nothing in this project needs one
yet). This script is meant to be invoked by something *outside* the app —
Railway's native cron-scheduled service (`deploy.cronSchedule` in service
config, a separate lightweight service built from the same Docker image
with this as its start command), a local cron entry, or manually — which
starts a container, runs this once, and lets it exit.

Run with:
    python -m app.workers.anomaly_runner

Exit code 0 on a clean run (regardless of how many monitors fired an
anomaly), non-zero only if the run itself failed unexpectedly (e.g. no
database connection) — individual monitor failures are captured as
per-monitor ERROR results and logged, not raised.
"""
import sys

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.logging import configure_logging, get_logger
from app.services.monitor_service import MonitorService
from app.storage import get_storage_provider

logger = get_logger(__name__)


def main() -> int:
    configure_logging(debug=settings.DEBUG)
    db = SessionLocal()
    try:
        service = MonitorService(db, get_storage_provider())
        results = service.run_due_monitors()
        anomalies = sum(1 for _, outcome in results if outcome.status == "ANOMALY_DETECTED")
        errors = sum(1 for _, outcome in results if outcome.status == "ERROR")
        logger.info(
            "anomaly_runner_completed",
            monitors_checked=len(results),
            anomalies_detected=anomalies,
            errors=errors,
        )
        return 0
    except Exception:
        logger.error("anomaly_runner_failed", exc_info=True)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
