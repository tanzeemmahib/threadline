from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.errors import register_error_handlers
from app.api.routes import api_router
from app.config import Settings, get_settings
from app.logging_config import configure_logging
from app.services.jobs import JobManager
from app.services.storage import SQLiteRepository


def create_app(settings: Settings | None = None) -> FastAPI:
    configure_logging()
    resolved = settings or get_settings()
    app = FastAPI(
        title=resolved.app_name,
        version=resolved.app_version,
        description=(
            "Research decision-support API using synthetic identities. It proposes candidate "
            "record connections and never autonomously determines identity."
        ),
    )
    app.state.settings = resolved
    app.state.repository = SQLiteRepository(resolved.database_path)
    app.state.job_manager = JobManager(
        app.state.repository,
        max_concurrent_jobs=resolved.max_concurrent_evaluation_jobs,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(resolved.frontend_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "Accept"],
    )
    register_error_handlers(app)
    app.include_router(api_router)
    return app


app = create_app()
