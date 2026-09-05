import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.dashboard import DashboardChart
from app.models.dataset import Dataset


class DashboardChartRepository:
    """Data-access layer for charts saved onto a dashboard."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def create(
        self,
        *,
        dashboard_id: uuid.UUID,
        dataset_id: uuid.UUID,
        title: str,
        chart_type: str,
        query_request: dict[str, Any],
    ) -> DashboardChart:
        next_position = self._db.execute(
            select(func.coalesce(func.max(DashboardChart.position), -1) + 1).where(
                DashboardChart.dashboard_id == dashboard_id
            )
        ).scalar_one()

        chart = DashboardChart(
            dashboard_id=dashboard_id,
            dataset_id=dataset_id,
            title=title,
            chart_type=chart_type,
            query_request=query_request,
            position=next_position,
        )
        self._db.add(chart)
        self._db.commit()
        self._db.refresh(chart)
        return chart

    def list_for_dashboard(self, dashboard_id: uuid.UUID) -> list[tuple[DashboardChart, str]]:
        """Returns (chart, dataset_filename) pairs, in display order."""
        stmt = (
            select(DashboardChart, Dataset.original_filename)
            .join(Dataset, Dataset.id == DashboardChart.dataset_id)
            .where(DashboardChart.dashboard_id == dashboard_id)
            .order_by(DashboardChart.position.asc())
        )
        return [(row[0], row[1]) for row in self._db.execute(stmt).all()]

    def get(self, chart_id: uuid.UUID, dashboard_id: uuid.UUID) -> DashboardChart | None:
        stmt = select(DashboardChart).where(
            DashboardChart.id == chart_id, DashboardChart.dashboard_id == dashboard_id
        )
        return self._db.execute(stmt).scalar_one_or_none()

    def swap_positions(self, a: DashboardChart, b: DashboardChart) -> None:
        a.position, b.position = b.position, a.position
        self._db.add_all([a, b])
        self._db.commit()

    def get_neighbor(self, chart: DashboardChart, *, direction: str) -> DashboardChart | None:
        stmt = select(DashboardChart).where(DashboardChart.dashboard_id == chart.dashboard_id)
        if direction == "up":
            stmt = stmt.where(DashboardChart.position < chart.position).order_by(
                DashboardChart.position.desc()
            )
        else:
            stmt = stmt.where(DashboardChart.position > chart.position).order_by(
                DashboardChart.position.asc()
            )
        return self._db.execute(stmt.limit(1)).scalar_one_or_none()

    def delete(self, chart: DashboardChart) -> None:
        self._db.delete(chart)
        self._db.commit()
