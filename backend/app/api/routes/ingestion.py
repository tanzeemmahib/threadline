from typing import Literal

from fastapi import APIRouter

from app.schemas.models import AnalyzeRequest, CasePackage, CasePackageInput
from app.services.ingestion import ingest_case_package
from app.v1_demo import v1_analyze_request, v1_case_package

router = APIRouter(prefix="/api/v1", tags=["ingestion"])


@router.post("/case-packages/ingest", response_model=CasePackage)
async def ingest_package(payload: CasePackageInput) -> CasePackage:
    return ingest_case_package(payload)


@router.get("/demo/v1/{scenario}/package", response_model=CasePackage)
async def get_v1_package(
    scenario: Literal["passing", "blocked", "review", "rival"],
) -> CasePackage:
    return v1_case_package(scenario)


@router.get("/demo/v1/{scenario}", response_model=AnalyzeRequest)
async def get_v1_demo(
    scenario: Literal["passing", "blocked", "review", "rival"],
) -> AnalyzeRequest:
    return v1_analyze_request(scenario)
