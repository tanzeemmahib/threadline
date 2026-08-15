from fastapi import APIRouter

from app.api.routes.ablation import router as ablation_router
from app.api.routes.analyze import router as analyze_router
from app.api.routes.baselines import router as baselines_router
from app.api.routes.benchmark import router as benchmark_router
from app.api.routes.contracts import router as contracts_router
from app.api.routes.counterfactuals import router as counterfactuals_router
from app.api.routes.demo import router as demo_router
from app.api.routes.health import router as health_router
from app.api.routes.ingestion import router as ingestion_router
from app.api.routes.integrity import router as integrity_router
from app.api.routes.jobs import router as jobs_router
from app.api.routes.persistence import router as persistence_router
from app.api.routes.replays import router as replays_router
from app.api.routes.results import router as results_router
from app.api.routes.reviews import router as reviews_router
from app.api.routes.trials import router as trials_router

api_router = APIRouter()
for router in (
    health_router,
    analyze_router,
    baselines_router,
    benchmark_router,
    ablation_router,
    demo_router,
    ingestion_router,
    persistence_router,
    contracts_router,
    integrity_router,
    replays_router,
    counterfactuals_router,
    reviews_router,
    trials_router,
    results_router,
    jobs_router,
):
    api_router.include_router(router)
