from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from app.schemas.models import (
    ExportManifest,
    ExportRequest,
    ReportResponse,
    StoredResult,
    StoredResultSummary,
)
from app.services.exports import export_result
from app.services.reports import build_research_report

router = APIRouter(prefix="/api/v1", tags=["results"])


def _get_result(result_id: str, request: Request) -> StoredResult:
    value = request.app.state.repository.get("results", result_id)
    if value is None:
        raise HTTPException(status_code=404, detail="Stored result not found")
    return StoredResult.model_validate(value)


@router.get("/results", response_model=list[StoredResultSummary])
async def list_results(
    request: Request, limit: int = Query(default=50, ge=1, le=500)
) -> list[StoredResultSummary]:
    results = [
        StoredResult.model_validate(item)
        for item in request.app.state.repository.list_items("results", limit=limit)
    ]
    return [
        StoredResultSummary(
            result_id=item.result_id,
            result_type=item.result_type,
            created_at=item.created_at,
            provider_mode=item.provider_mode,
        )
        for item in results
    ]


@router.get("/results/{result_id}", response_model=StoredResult)
async def get_result(result_id: str, request: Request) -> StoredResult:
    return _get_result(result_id, request)


@router.post("/results/{result_id}/export", response_model=ExportManifest)
async def create_export(result_id: str, payload: ExportRequest, request: Request) -> ExportManifest:
    result = _get_result(result_id, request)
    manifest = export_result(result, payload, request.app.state.settings.export_directory)
    request.app.state.repository.put("exports", manifest.export_id, manifest)
    return manifest


@router.post("/results/{result_id}/report", response_model=ReportResponse)
async def create_report(result_id: str, request: Request) -> ReportResponse:
    report = build_research_report(_get_result(result_id, request))
    request.app.state.repository.put("reports", report.report_id, report)
    return report
