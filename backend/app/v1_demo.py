from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from app.schemas.models import AnalyzeOptions, AnalyzeRequest, CasePackage, CasePackageInput
from app.services.ingestion import ingest_case_package

V1Scenario = Literal["passing", "blocked", "review", "rival"]

SCENARIO_RECORDS: dict[V1Scenario, tuple[str, ...]] = {
    "passing": ("FAMILY-018", "SHELTER-204"),
    "blocked": ("FAMILY-018", "HOSPITAL-052"),
    "review": ("EVAC-089", "VOLUNTEER-012", "SHELTER-AMB-002"),
    "rival": ("FAMILY-018", "SHELTER-204", "HOSPITAL-052"),
}


def v1_case_package(scenario: V1Scenario) -> CasePackage:
    fixture_path = Path(__file__).parents[1] / "fixtures" / "v1_case_package.json"
    fixture = CasePackageInput.model_validate(json.loads(fixture_path.read_text("utf-8")))
    wanted = set(SCENARIO_RECORDS[scenario])
    records = [record for record in fixture.records if record.record_id in wanted]
    incident = fixture.incident.model_copy(deep=True)
    incident.incident_id = f"INCIDENT-V1-{scenario.upper()}"
    incident.name = f"Synthetic North District V1 — {scenario.title()} scenario"
    if scenario == "blocked":
        incident.reviewer_constraints = [
            *incident.reviewer_constraints,
            "Withhold unresolved hard conflicts",
        ]
    return ingest_case_package(
        CasePackageInput(
            package_id=f"PACKAGE-V1-{scenario.upper()}",
            incident=incident,
            records=records,
        )
    )


def v1_analyze_request(scenario: V1Scenario) -> AnalyzeRequest:
    package = v1_case_package(scenario)
    return AnalyzeRequest(
        incident=package.incident,
        records=package.records,
        options=AnalyzeOptions(provider_mode="mock", candidate_limit=5),
    )
