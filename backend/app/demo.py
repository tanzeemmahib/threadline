from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from app.schemas.models import AnalyzeOptions, AnalyzeRequest, IncidentInput, RecordInput


@lru_cache
def demo_request() -> AnalyzeRequest:
    fixture_dir = Path(__file__).parents[1] / "fixtures"
    incident = IncidentInput.model_validate_json(
        (fixture_dir / "demo_incident.json").read_text("utf-8")
    )
    records_data = json.loads((fixture_dir / "demo_records.json").read_text("utf-8"))
    records = [RecordInput.model_validate(item) for item in records_data]
    return AnalyzeRequest(
        incident=incident,
        records=records,
        options=AnalyzeOptions(provider_mode="mock", candidate_limit=5),
    )
