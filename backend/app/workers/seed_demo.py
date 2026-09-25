"""Idempotent public-demo seeder — docs/PHASES.md Phase 8 step 6 ("demo
account + sample dataset so a recruiter can try it in under a minute").

    python -m app.workers.seed_demo

Runs at container start (backend/Dockerfile) and does nothing unless
DEMO_USER_EMAIL and DEMO_USER_PASSWORD are both set. When they are, it
converges the demo account to a known-good state every time:

- the demo user exists, and its password matches the configured one (so
  rotating the demo password is just an env-var change);
- exactly one healthy sample dataset exists — "healthy" meaning profiled
  AND its file actually present in storage. That second check matters: on
  local-disk storage (docs/STORAGE.md), a redeploy wipes uploaded files
  but not their database rows, leaving a dataset that lists fine and then
  fails to load. Broken copies are deleted and a fresh one uploaded;
- a demo dashboard exists with a chart on that dataset.

It never blocks startup: any failure is logged and the process exits 0.
A demo that's temporarily broken is better than an API that won't boot.

The demo dataset is the eval harness's e-commerce set
(evals/datasets/ecommerce.csv) — deliberately full of real data-quality
issues (duplicates, missing values, impossible ages, a revenue formula
mismatch, a large outlier), so the AI Analyst has something genuinely
interesting to find in a first question.
"""
import sys
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.logging import configure_logging, get_logger
from app.core.security import hash_password, verify_password
from app.models.dashboard import Dashboard
from app.models.dataset import Dataset
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.dashboard import DashboardChartCreate
from app.schemas.dataset_query import Aggregation, DatasetQueryRequest
from app.services.dashboard_service import DashboardService
from app.services.dataset_service import DatasetService
from app.storage import StorageProvider, get_storage_provider

logger = get_logger(__name__)

DEMO_FILENAME = "pulseiq_demo_sales.csv"
DEMO_DASHBOARD_NAME = "Demo — Sales overview"
_DEMO_CSV = Path(__file__).parent / "demo_data" / DEMO_FILENAME
_REVENUE_BY_CATEGORY = DatasetQueryRequest(
    group_by=["category"],
    aggregations=[Aggregation(op="sum", column="revenue", alias="total_revenue")],
    sort_by="total_revenue",
    sort_desc=True,
)


def _ensure_user(db: Session, email: str, password: str) -> User:
    repo = UserRepository(db)
    user = repo.get_by_email(email)
    if user is None:
        user = repo.create(
            email=email, hashed_password=hash_password(password), full_name="Demo user"
        )
        logger.info("demo_user_created", user_id=str(user.id))
    elif not verify_password(password, user.hashed_password):
        user.hashed_password = hash_password(password)
        db.commit()
        logger.info("demo_user_password_synced", user_id=str(user.id))
    return user


def _is_healthy(dataset: Dataset, storage: StorageProvider) -> bool:
    return dataset.status == "profiled" and storage.exists(dataset.storage_key)


def _ensure_dataset(db: Session, storage: StorageProvider, owner_id: uuid.UUID) -> Dataset:
    datasets = DatasetService(db, storage)
    existing = db.execute(
        select(Dataset).where(
            Dataset.owner_id == owner_id, Dataset.original_filename == DEMO_FILENAME
        )
    ).scalars().all()

    healthy: Dataset | None = None
    for dataset in existing:
        if healthy is None and _is_healthy(dataset, storage):
            healthy = dataset
            continue
        # A broken copy (file wiped by a redeploy) or a duplicate — remove
        # it. delete_owned deletes the row first and tolerates the file
        # already being gone.
        logger.info("demo_dataset_removed", dataset_id=str(dataset.id), healthy=False)
        datasets.delete_owned(dataset.id, owner_id)

    if healthy is not None:
        return healthy

    uploaded = datasets.upload(
        owner_id=owner_id,
        filename=DEMO_FILENAME,
        content_type="text/csv",
        data=_DEMO_CSV.read_bytes(),
    )
    logger.info("demo_dataset_uploaded", dataset_id=str(uploaded.id), status=uploaded.status)
    return uploaded


def _ensure_dashboard(db: Session, owner_id: uuid.UUID, dataset_id: uuid.UUID) -> None:
    dashboards = DashboardService(db)
    dashboard = db.execute(
        select(Dashboard).where(
            Dashboard.owner_id == owner_id, Dashboard.name == DEMO_DASHBOARD_NAME
        )
    ).scalars().first()
    if dashboard is not None:
        dashboard_id = dashboard.id
    else:
        dashboard_id = dashboards.create(owner_id, DEMO_DASHBOARD_NAME).id

    detail = dashboards.get_detail(dashboard_id, owner_id)
    if any(chart.dataset_id == dataset_id for chart in detail.charts):
        return
    dashboards.add_chart(
        dashboard_id,
        owner_id,
        DashboardChartCreate(
            dataset_id=dataset_id,
            title="Revenue by category",
            chart_type="bar",
            query=_REVENUE_BY_CATEGORY,
        ),
    )
    logger.info("demo_dashboard_chart_added", dashboard_id=str(dashboard_id))


def seed_demo(db: Session, storage: StorageProvider) -> bool:
    """Returns whether the demo was seeded (False = not configured)."""
    email, password = settings.DEMO_USER_EMAIL, settings.DEMO_USER_PASSWORD
    if not email or not password:
        logger.info("demo_seed_skipped", reason="DEMO_USER_EMAIL/DEMO_USER_PASSWORD not set")
        return False
    user = _ensure_user(db, email, password)
    dataset = _ensure_dataset(db, storage, user.id)
    _ensure_dashboard(db, user.id, dataset.id)
    logger.info("demo_seed_complete", user_id=str(user.id), dataset_id=str(dataset.id))
    return True


def main() -> int:
    configure_logging(debug=settings.DEBUG)
    db = SessionLocal()
    try:
        seed_demo(db, get_storage_provider())
    except Exception:  # noqa: BLE001 - never block the API from starting
        logger.exception("demo_seed_failed")
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
