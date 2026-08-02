from __future__ import annotations

from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from app.providers.base import ModelProvider, ProviderFailure
from app.schemas.models import ProviderMetadata, ProviderResult

ModelT = TypeVar("ModelT", bound=BaseModel)


class MockProvider(ModelProvider[ModelT]):
    mode = "mock"
    model_name = "deterministic-fixture"

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
        del system_prompt, user_prompt
        try:
            output = response_model.model_validate(mock_payload)
        except ValidationError as exc:
            raise ProviderFailure(
                "MODEL_RESPONSE_SCHEMA_FAILURE",
                f"Deterministic provider fixture failed schema validation: {exc}",
            ) from exc
        return ProviderResult(
            output=output,
            metadata=ProviderMetadata(
                provider=self.mode,
                model=self.model_name,
                prompt_template_id=template_id,
                prompt_template_version=template_version,
                attempts=1,
                duration_ms=None,
                token_usage=None,
            ),
        )
