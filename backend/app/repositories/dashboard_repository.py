import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.dashboard import Dashboard, DashboardChart


class DashboardRepository:
    """Data-access layer for dashboards. Keeps ORM/session details out of services."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def create(self, *, owner_id: uuid.UUID, name: str) -> Dashboard:
        dashboard = Dashboard(owner_id=owner_id, name=name)
        self._db.add(dashboard)
        self._db.commit()
        self._db.refresh(dashboard)
        return dashboard

    def list_for_owner(self, owner_id: uuid.UUID) -> list[tuple[Dashboard, int]]:
        """Returns (dashboard, chart_count) pairs, newest first."""
        stmt = (
            select(Dashboard, func.count(DashboardChart.id))
            .outerjoin(DashboardChart, DashboardChart.dashboard_id == Dashboard.id)
            .where(Dashboard.owner_id == owner_id)
            .group_by(Dashboard.id)
            .order_by(Dashboard.created_at.desc())
        )
        return [(row[0], row[1]) for row in self._db.execute(stmt).all()]

    def get_owned(self, dashboard_id: uuid.UUID, owner_id: uuid.UUID) -> Dashboard | None:
        stmt = select(Dashboard).where(Dashboard.id == dashboard_id, Dashboard.owner_id == owner_id)
        return self._db.execute(stmt).scalar_one_or_none()

    def delete(self, dashboard: Dashboard) -> None:
        self._db.delete(dashboard)
        self._db.commit()
