from __future__ import annotations

import logging
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.providers.base import ProviderFailure
from app.schemas.models import ApiError, ErrorBody
from app.workflow.orchestrator import NodeExecutionError

logger = logging.getLogger(__name__)


def error_response(
    *,
    status_code: int,
    code: str,
    message: str,
    retryable: bool = False,
    failed_stage: str | None = None,
    details: dict | None = None,  # type: ignore[type-arg]
) -> JSONResponse:
    body = ApiError(
        error=ErrorBody(
            request_id=str(uuid4()),
            error_code=code,
            message=message,
            retryable=retryable,
            failed_stage=failed_stage,
            preserved_data=True,
            details=details or {},
        )
    )
    return JSONResponse(status_code=status_code, content=body.model_dump(mode="json"))


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def request_validation_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        del request
        errors = [
            {
                "type": item.get("type"),
                "location": list(item.get("loc", ())),
                "message": item.get("msg"),
            }
            for item in exc.errors()
        ]
        return error_response(
            status_code=422,
            code="INVALID_RECORD_INPUT",
            message="Request validation failed.",
            details={"errors": errors},
        )

    @app.exception_handler(ProviderFailure)
    async def provider_failure_handler(request: Request, exc: ProviderFailure) -> JSONResponse:
        del request
        return error_response(
            status_code=503 if exc.retryable else 422,
            code=exc.code,
            message=str(exc),
            retryable=exc.retryable,
            failed_stage="provider",
        )

    @app.exception_handler(NodeExecutionError)
    async def node_failure_handler(request: Request, exc: NodeExecutionError) -> JSONResponse:
        del request
        code = "INVALID_RECORD_INPUT" if exc.node_id == "incident" else "WORKFLOW_PARTIAL_FAILURE"
        return error_response(
            status_code=422,
            code=code,
            message=str(exc),
            failed_stage=exc.node_id,
        )

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
        del request
        return error_response(
            status_code=422,
            code="BENCHMARK_CONFIGURATION_INVALID",
            message=str(exc),
        )

    @app.exception_handler(Exception)
    async def unexpected_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception(
            "Unhandled request failure", exc_info=exc, extra={"path": request.url.path}
        )
        return error_response(
            status_code=500,
            code="INTERNAL_ERROR",
            message="An unexpected server error occurred.",
            failed_stage=None,
        )
