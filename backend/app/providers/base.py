from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

from app.schemas.models import ProviderResult

ModelT = TypeVar("ModelT", bound=BaseModel)


class ProviderFailure(RuntimeError):
    def __init__(self, code: str, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable


class ModelProvider(ABC, Generic[ModelT]):
    mode: str
    model_name: str | None

    @abstractmethod
    async def generate_structured(
        self,
        *,
        template_id: str,
        template_version: str,
        system_prompt: str,
        user_prompt: str,
        response_model: type[ModelT],
        mock_payload: dict[str, Any],
    ) -> ProviderResult:
        """Generate and validate one structured response, retrying once when appropriate."""


class DeterministicPayload(BaseModel):
    payload: dict[str, Any]
