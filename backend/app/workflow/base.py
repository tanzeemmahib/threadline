from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.models import ProviderMetadata, ValidationResult
from app.workflow.context import WorkflowContext


class NodeOutcome(BaseModel):
    summary: str
    data: dict[str, Any] = Field(default_factory=dict)
    validation_results: list[ValidationResult] = Field(default_factory=list)
    evidence_span_ids: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    abstention_reason: str | None = None
    provider_metadata: list[ProviderMetadata] = Field(default_factory=list)


class WorkflowNode(ABC):
    node_id: str
    version = "1.0.0"
    order: int
    name: str
    short_name: str
    category: str
    purpose: str
    uses_llm: bool
    requires_human_input: bool
    can_disable: bool
    input_schema: str
    output_schema: str
    failure_condition: str
    constraints: tuple[str, ...]

    @abstractmethod
    async def run(self, context: WorkflowContext) -> NodeOutcome: ...
