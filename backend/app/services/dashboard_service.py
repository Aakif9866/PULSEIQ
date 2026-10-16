import uuid
from typing import cast

from sqlalchemy.orm import Session

from app.core.exceptions import (
    ChartNotFoundError,
    DashboardNotFoundError,
    DatasetNotFoundError,
    InsightNotFoundError,
)
from app.models.dashboard import Dashboard
from app.repositories.dashboard_chart_repository import DashboardChartRepository
from app.repositories.dashboard_repository import DashboardRepository
from app.repositories.dataset_repository import DatasetRepository
from app.repositories.insight_repository import InsightRepository
from app.schemas.dashboard import (
    ChartType,
    ChartUpdate,
    DashboardChartCreate,
    DashboardChartRead,
    DashboardDetail,
    DashboardRead,
)
from app.schemas.dataset_query import DatasetQueryRequest


class DashboardService:
    def __init__(self, db: Session) -> None:
        self._dashboards = DashboardRepository(db)
        self._charts = DashboardChartRepository(db)
        self._datasets = DatasetRepository(db)
        self._insights = InsightRepository(db)

    def create(self, owner_id: uuid.UUID, name: str) -> DashboardRead:
        dashboard = self._dashboards.create(owner_id=owner_id, name=name)
        return DashboardRead(
            id=dashboard.id, name=dashboard.name, chart_count=0, created_at=dashboard.created_at
        )

    def list_for_owner(self, owner_id: uuid.UUID) -> list[DashboardRead]:
        return [
            DashboardRead(id=d.id, name=d.name, chart_count=count, created_at=d.created_at)
            for d, count in self._dashboards.list_for_owner(owner_id)
        ]

    def get_detail(self, dashboard_id: uuid.UUID, owner_id: uuid.UUID) -> DashboardDetail:
        dashboard = self._get_owned_dashboard(dashboard_id, owner_id)
        charts = [
            DashboardChartRead(
                id=chart.id,
                dataset_id=chart.dataset_id,
                dataset_filename=filename,
                title=chart.title,
                chart_type=cast(ChartType, chart.chart_type),
                query_request=DatasetQueryRequest.model_validate(chart.query_request),
                insight_id=chart.insight_id,
                position=chart.position,
                created_at=chart.created_at,
            )
            for chart, filename in self._charts.list_for_dashboard(dashboard_id)
        ]
        return DashboardDetail(
            id=dashboard.id, name=dashboard.name, created_at=dashboard.created_at, charts=charts
        )

    def delete(self, dashboard_id: uuid.UUID, owner_id: uuid.UUID) -> None:
        dashboard = self._get_owned_dashboard(dashboard_id, owner_id)
        self._dashboards.delete(dashboard)

    def add_chart(
        self, dashboard_id: uuid.UUID, owner_id: uuid.UUID, payload: DashboardChartCreate
    ) -> DashboardChartRead:
        self._get_owned_dashboard(dashboard_id, owner_id)

        # dataset_id is client-supplied, so re-verify ownership rather than trusting it.
        dataset = self._datasets.get_owned(payload.dataset_id, owner_id)
        if dataset is None:
            raise DatasetNotFoundError(payload.dataset_id)
        # Same for the insight link: it must be this user's, on this dataset.
        if payload.insight_id is not None:
            insight = self._insights.get_owned(payload.insight_id, owner_id)
            if insight is None or insight.dataset_id != payload.dataset_id:
                raise InsightNotFoundError(payload.insight_id)

        chart = self._charts.create(
            dashboard_id=dashboard_id,
            dataset_id=payload.dataset_id,
            title=payload.title,
            chart_type=payload.chart_type,
            query_request=payload.query.model_dump(),
            insight_id=payload.insight_id,
        )
        return DashboardChartRead(
            id=chart.id,
            dataset_id=chart.dataset_id,
            dataset_filename=dataset.original_filename,
            title=chart.title,
            chart_type=payload.chart_type,
            query_request=payload.query,
            insight_id=chart.insight_id,
            position=chart.position,
            created_at=chart.created_at,
        )

    def rename_chart(
        self,
        dashboard_id: uuid.UUID,
        owner_id: uuid.UUID,
        chart_id: uuid.UUID,
        payload: ChartUpdate,
    ) -> None:
        self._get_owned_dashboard(dashboard_id, owner_id)
        chart = self._charts.get(chart_id, dashboard_id)
        if chart is None:
            raise ChartNotFoundError(chart_id)
        self._charts.rename(chart, payload.title.strip())

    def delete_chart(
        self, dashboard_id: uuid.UUID, owner_id: uuid.UUID, chart_id: uuid.UUID
    ) -> None:
        self._get_owned_dashboard(dashboard_id, owner_id)
        chart = self._charts.get(chart_id, dashboard_id)
        if chart is None:
            raise ChartNotFoundError(chart_id)
        self._charts.delete(chart)

    def move_chart(
        self, dashboard_id: uuid.UUID, owner_id: uuid.UUID, chart_id: uuid.UUID, direction: str
    ) -> None:
        self._get_owned_dashboard(dashboard_id, owner_id)
        chart = self._charts.get(chart_id, dashboard_id)
        if chart is None:
            raise ChartNotFoundError(chart_id)

        neighbor = self._charts.get_neighbor(chart, direction=direction)
        if neighbor is not None:
            self._charts.swap_positions(chart, neighbor)

    def _get_owned_dashboard(self, dashboard_id: uuid.UUID, owner_id: uuid.UUID) -> Dashboard:
        dashboard = self._dashboards.get_owned(dashboard_id, owner_id)
        if dashboard is None:
            raise DashboardNotFoundError(dashboard_id)
        return dashboard
