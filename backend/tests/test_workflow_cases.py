from __future__ import annotations

import pytest

from app.config import Settings
from app.demo import demo_request
from app.providers.mock_provider import MockProvider
from app.schemas.models import AnalyzeRequest
from app.workflow import WorkflowOrchestrator


async def run_subset(record_ids: set[str]) -> tuple[AnalyzeRequest, object]:
    request = demo_request().model_copy(deep=True)
    request.records = [record for record in request.records if record.record_id in record_ids]
    response = await WorkflowOrchestrator(settings=Settings(), provider=MockProvider()).run(request)
    return request, response


@pytest.mark.asyncio
async def test_canonical_candidate_case() -> None:
    _, response = await run_subset({"FAMILY-018", "SHELTER-204"})
    assert response.candidates[0].classification_code.value == "possible_candidate"
    assert len(response.workflow_trace_details) == 12


@pytest.mark.asyncio
async def test_hard_conflict_case() -> None:
    _, response = await run_subset({"FAMILY-018", "HOSPITAL-052"})
    assert response.candidates[0].classification_code.value == "conflicting_evidence"
    assert response.summary.hard_conflicts == 1


@pytest.mark.asyncio
async def test_required_abstention_with_two_rivals() -> None:
    _, response = await run_subset({"EVAC-089", "VOLUNTEER-012", "SHELTER-AMB-002"})
    assert response.candidates[0].classification_code.value == "insufficient_evidence"
    assert response.status == "insufficient_evidence"
    assert any(
        "rival ambiguity" in reason.lower() for reason in response.candidates[0].abstention_reasons
    )


@pytest.mark.asyncio
async def test_prompt_injection_is_quarantined() -> None:
    _, response = await run_subset({"FAMILY-018", "PHONE-066"})
    phone = next(record for record in response.records if record.record_id == "PHONE-066")
    assert phone.quarantined
    assert phone.text.startswith("Caller reports")
    assert "QUARANTINED" in phone.safe_text


@pytest.mark.asyncio
async def test_multilingual_original_is_preserved() -> None:
    _, response = await run_subset({"FAMILY-018", "SHELTER-204"})
    family = next(record for record in response.records if record.record_id == "FAMILY-018")
    assert "يوسف الحسن" in family.text
    assert "يوسف الحسن" in family.normalized_names


@pytest.mark.asyncio
async def test_translation_loss_warning() -> None:
    _, response = await run_subset({"PHONE-071", "SHELTER-204"})
    translated = next(record for record in response.records if record.record_id == "PHONE-071")
    assert translated.translation_warning
    assert any(span.field == "Distinctive features" for span in translated.evidence_spans)
