import pytest

from app.config import Settings
from app.providers.mock_provider import MockProvider
from app.schemas.models import AnalyzeRequest, NormalizedRecord
from app.services.timeline_rules import minutes_from_text, timeline_compatibility
from app.workflow import WorkflowOrchestrator


def test_timeline_compatibility_and_negative_order() -> None:
    earlier = NormalizedRecord(
        record_id="A",
        source_type="note",
        language="English",
        text="Seen at 7:10 p.m.",
        display_name="A",
        safe_text="Seen at 7:10 p.m.",
    )
    later = NormalizedRecord(
        record_id="B",
        source_type="note",
        language="English",
        text="Seen at 4:30 p.m.",
        display_name="B",
        safe_text="Seen at 4:30 p.m.",
    )
    assert minutes_from_text(earlier.text) == 1150
    assert not timeline_compatibility(earlier, later).passed


@pytest.mark.asyncio
async def test_phone_blocking_retrieves_canonical_pair(demo: AnalyzeRequest) -> None:
    """The canonical Arabic–English pair FAMILY-018 + SHELTER-204 must be the top result.

    Currently uses shared phone (0501234567) as the primary blocking key.
    Cross-script name matching (Arabic ↔ English) via consonant skeleton
    provides additional supporting evidence.
    """
    demo.records = demo.records[:3]
    response = await WorkflowOrchestrator(settings=Settings(), provider=MockProvider()).run(demo)
    top = response.candidates[0]
    assert {top.record_a_id, top.record_b_id} == {"FAMILY-018", "SHELTER-204"}
    assert top.classification_code.value == "possible_candidate"
    assert "probability" not in top.model_dump_json().lower()
    if response.operational.get("deterministic_pipeline"):
        assert top.linkage_decision_state is not None


@pytest.mark.asyncio
async def test_cross_script_retrieval_limited_by_mock_extraction(demo: AnalyzeRequest) -> None:
    """Cross-script retrieval (Arabic ↔ English) is limited by mock extraction.

    FAMILY-018 (Arabic) and SHELTER-204 (English) describe the same person
    but cannot be paired by name alone because the mock extractor does not
    produce transliterated name forms usable by blocking rules. Once a
    transliteration-aware blocking rule is added, this test should assert
    that the canonical pair is found without requiring a shared phone.
    """
    # This test documents the current limitation; it does not assert retrieval
    # because cross-script blocking is not yet implemented.
    demo.records = demo.records[:3]
    response = await WorkflowOrchestrator(settings=Settings(), provider=MockProvider()).run(demo)
    # The pipeline produces at least one candidate (HOSPITAL-052 + SHELTER-204)
    assert len(response.candidates) >= 1
    # Both records are valid demo records
    valid_ids = {"FAMILY-018", "SHELTER-204", "HOSPITAL-052"}
    for c in response.candidates:
        assert c.record_a_id in valid_ids
        assert c.record_b_id in valid_ids
