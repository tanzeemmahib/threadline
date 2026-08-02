from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from app.schemas.models import ReportResponse, StoredResult
from app.services.exports import _markdown


def build_research_report(result: StoredResult) -> ReportResponse:
    return ReportResponse(
        report_id=f"REPORT-{uuid4()}",
        result_id=result.result_id,
        created_at=datetime.now(UTC),
        markdown=_markdown(result),
    )
