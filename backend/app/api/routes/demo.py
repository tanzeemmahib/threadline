from fastapi import APIRouter

from app.demo import demo_request
from app.schemas.models import AnalyzeRequest

router = APIRouter(prefix="/api/v1", tags=["demo"])


@router.get("/demo", response_model=AnalyzeRequest)
async def demo() -> AnalyzeRequest:
    return demo_request().model_copy(deep=True)
