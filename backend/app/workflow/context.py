from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.config import Settings
from app.providers.base import ModelProvider
from app.schemas.linkage import LinkageDecision
from app.schemas.models import (
    AdjudicationModelOutput,
    AnalyzeRequest,
    CandidateConnection,
    HypothesisModelOutput,
    NormalizedRecord,
    ProsecutorModelOutput,
)
from app.services.audit import AuditBuilder


@dataclass(slots=True)
class WorkflowContext:
    request: AnalyzeRequest
    settings: Settings
    provider: ModelProvider  # type: ignore[type-arg]
    audit: AuditBuilder
    records: list[NormalizedRecord] = field(default_factory=list)
    candidates: list[CandidateConnection] = field(default_factory=list)
    timeline_events: list[dict[str, Any]] = field(default_factory=list)
    hypotheses: dict[str, HypothesisModelOutput] = field(default_factory=dict)
    prosecutor_reports: dict[str, ProsecutorModelOutput] = field(default_factory=dict)
    adjudications: dict[str, list[AdjudicationModelOutput]] = field(default_factory=dict)
    redactions: list[dict[str, str]] = field(default_factory=list)
    model_calls: int = 0
    retries: int = 0
    # ── New identity-resolution fields ──
    linkage_decisions: dict[str, LinkageDecision] = field(default_factory=dict)
    raw_comparisons: dict[str, list[Any]] = field(default_factory=dict)
    candidate_generation_rules: dict[str, list[str]] = field(default_factory=dict)

    @property
    def mock_mode(self) -> bool:
        return self.request.options.provider_mode.value == "mock"

    @property
    def disabled_nodes(self) -> set[str]:
        return set(self.request.options.disabled_nodes)
