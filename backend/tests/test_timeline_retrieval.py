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
async def test_fuzzy_candidate_retrieval_prefers_canonical_pair(demo: AnalyzeRequest) -> None:
    demo.records = demo.records[:3]
    response = await WorkflowOrchestrator(settings=Settings(), provider=MockProvider()).run(demo)
    top = response.candidates[0]
    assert {top.record_a_id, top.record_b_id} == {"FAMILY-018", "SHELTER-204"}
    assert top.classification_code.value == "possible_candidate"
    assert "probability" not in top.model_dump_json().lower()
