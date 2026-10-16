import json
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.core.exceptions import DatasetNotFoundError, InsightNotFoundError
from app.models.insight import Insight
from app.repositories.dataset_repository import DatasetRepository
from app.repositories.insight_repository import InsightRepository
from app.schemas.analysis import Finding, ToolCallRecord
from app.schemas.dataset_query import DatasetQueryRequest
from app.schemas.insight import InsightCreate, InsightRead, InsightUpdate


class InsightService:
    def __init__(self, db: Session) -> None:
        self._repo = InsightRepository(db)
        self._datasets = DatasetRepository(db)

    def save(self, owner_id: uuid.UUID, payload: InsightCreate) -> InsightRead:
        # dataset_id is client-supplied (round-tripped from an /ask response),
        # so re-verify ownership rather than trusting it.
        dataset = self._datasets.get_owned(payload.dataset_id, owner_id)
        if dataset is None:
            raise DatasetNotFoundError(payload.dataset_id)

        # The client sends both findings and evidence; never trust its
        # "verified" flags. Re-check every finding against the computations
        # being stored with it, exactly as the analysis itself does.
        if payload.findings:
            from app.ai.answer_validator import validate_findings

            validate_findings(payload.findings, payload.tool_calls)

        insight = self._repo.create(
            owner_id=owner_id,
            dataset_id=payload.dataset_id,
            question=payload.question,
            answer=payload.answer,
            query_request=payload.query.model_dump() if payload.query else None,
            row_count=payload.row_count,
            findings=[f.model_dump() for f in payload.findings] or None,
            title=(payload.title or payload.question)[:255],
            tool_calls=_compact_tool_calls(payload.tool_calls) or None,
            dataset_version=dataset.version,
        )
        return _to_read(insight, dataset.original_filename, dataset.version)

    def list_for_owner(self, owner_id: uuid.UUID) -> list[InsightRead]:
        return [
            _to_read(insight, dataset_filename, version)
            for insight, dataset_filename, version in self._repo.list_for_owner(owner_id)
        ]

    def get_owned(self, insight_id: uuid.UUID, owner_id: uuid.UUID) -> InsightRead:
        found = self._repo.get_owned_with_filename(insight_id, owner_id)
        if found is None:
            raise InsightNotFoundError(insight_id)
        return _to_read(*found)

    def rename(
        self, insight_id: uuid.UUID, owner_id: uuid.UUID, payload: InsightUpdate
    ) -> InsightRead:
        found = self._repo.get_owned_with_filename(insight_id, owner_id)
        if found is None:
            raise InsightNotFoundError(insight_id)
        insight, filename, version = found
        return _to_read(self._repo.rename(insight, payload.title.strip()), filename, version)

    def report_html(self, insight_id: uuid.UUID, owner_id: uuid.UUID) -> tuple[str, str]:
        """(html, suggested filename) for a standalone report of one insight."""
        from app.services.report import render_insight_report

        insight = self.get_owned(insight_id, owner_id)
        dataset = self._datasets.get_owned(insight.dataset_id, owner_id)
        if dataset is None:
            raise DatasetNotFoundError(insight.dataset_id)
        return render_insight_report(insight, dataset), _report_filename(insight.title)

    def delete_owned(self, insight_id: uuid.UUID, owner_id: uuid.UUID) -> None:
        insight = self._repo.get_owned(insight_id, owner_id)
        if insight is None:
            raise InsightNotFoundError(insight_id)
        self._repo.delete(insight)


def _to_read(insight: Insight, dataset_filename: str, current_version: int) -> InsightRead:
    return InsightRead(
        id=insight.id,
        dataset_id=insight.dataset_id,
        dataset_filename=dataset_filename,
        title=insight.title or insight.question,
        question=insight.question,
        answer=insight.answer,
        query_request=(
            DatasetQueryRequest.model_validate(insight.query_request)
            if insight.query_request is not None
            else None
        ),
        row_count=insight.row_count,
        findings=[Finding.model_validate(f) for f in insight.findings or []],
        tool_calls=[ToolCallRecord.model_validate(t) for t in insight.tool_calls or []],
        dataset_version=insight.dataset_version,
        current_dataset_version=current_version,
        created_at=insight.created_at,
    )


# One tool result can be a whole table; stored evidence stays bounded.
_MAX_STORED_RESULT_CHARS = 6000


def _compact_tool_calls(calls: list[ToolCallRecord]) -> list[dict[str, Any]]:
    out = []
    for call in calls:
        record = call.model_dump()
        if len(json.dumps(record["result"], default=str)) > _MAX_STORED_RESULT_CHARS:
            record["result"] = {
                "omitted": "This result was too large to store; re-run the analysis to see it."
            }
        out.append(record)
    return out


def _report_filename(title: str) -> str:
    slug = "".join(c if c.isalnum() else "-" for c in title.lower()).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return f"pulseiq-report-{slug[:60] or 'insight'}.html"
