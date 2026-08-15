from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import pytest

from app.baselines.runner import BaselineRunner
from app.config import Settings
from app.evaluation.v1_evidence import build_v1_evaluation
from app.providers.mock_provider import MockProvider
from app.v1_demo import v1_analyze_request


class CapturingMockProvider(MockProvider[Any]):
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def generate_structured(self, **kwargs: Any) -> Any:
        self.calls.append(dict(kwargs))
        return await super().generate_structured(**kwargs)


@pytest.mark.asyncio
async def test_same_immutable_input_reaches_single_calls_and_full_workflow(
    settings: Settings,
) -> None:
    provider = CapturingMockProvider()
    request = v1_analyze_request("rival")
    expected_ids = [record.record_id for record in request.records]
    expected_text = {record.record_id: record.text for record in request.records}

    response = await BaselineRunner(settings=settings, provider=provider).run(request)
    outputs = {item.system_id: item for item in response.systems}

    prompt_calls = {
        call["template_id"]: call
        for call in provider.calls
        if call["template_id"] in {"generic_baseline", "structured_baseline"}
    }
    assert set(prompt_calls) == {"generic_baseline", "structured_baseline"}
    for call in prompt_calls.values():
        for record in request.records:
            assert f"record_id='{record.record_id}'" in call["user_prompt"]
            assert record.text in call["user_prompt"]
            assert record.source_type in call["user_prompt"]
            assert record.language in call["user_prompt"]
            if record.timestamp is not None:
                assert record.model_dump(mode="json")["timestamp"] in call["user_prompt"]

    manifests = [
        outputs[system_id].output["input_manifest"]
        for system_id in ("generic", "structured", "threadline")
    ]
    assert all(manifest["record_ids"] == expected_ids for manifest in manifests)
    assert len({manifest["input_sha256"] for manifest in manifests}) == 1
    assert len({manifest["available_evidence_sha256"] for manifest in manifests}) == 1
    assert all(len(outputs[system_id].candidate_record_ids) == 2 for system_id in ("generic", "structured"))

    workflow_records = outputs["threadline"].output["workflow_response"]["records"]
    assert {record["record_id"]: record["text"] for record in workflow_records} == expected_text


@pytest.mark.asyncio
async def test_v1_evaluation_regenerates_with_truthful_risk_denominators(
    settings: Settings,
) -> None:
    artifact = await build_v1_evaluation(settings)
    holdout_metrics = {metric.metric_id: metric for metric in artifact.holdout.metrics}

    assert artifact.artifact_version == "threadline-v1-evaluation/1.1.0"
    assert artifact.holdout.case_count == 40
    assert artifact.risk_bound.observed_unsafe_releases == 0
    assert artifact.risk_bound.negative_cases == 4
    assert artifact.risk_bound.all_case_upper_bound_percent == pytest.approx(8.762)
    assert artifact.risk_bound.conditional_negative_upper_bound_percent == pytest.approx(48.989)
    assert artifact.risk_bound.upper_bound_percent == pytest.approx(48.989)
    assert artifact.risk_bound.target_status == "not_met"
    assert "candidate_top_1_recall" in holdout_metrics
    assert "candidate_recall_at_5" not in holdout_metrics
    assert "whole_record_removal_decision_change_rate" in holdout_metrics


def test_locked_submission_artifacts_reconcile() -> None:
    repository_root = Path(__file__).resolve().parents[2]
    submission = repository_root / "docs" / "submission"
    artifact_paths = [
        submission / "results.json",
        submission / "raw-outputs.json",
        submission / "ablation-counterfactual.json",
        submission / "results.csv",
        submission / "benchmark-report.md",
    ]
    for path in artifact_paths:
        text = path.read_text("utf-8")
        assert "â" not in text
        assert "\ufffd" not in text
    results = json.loads(artifact_paths[0].read_text("utf-8"))
    raw = json.loads(artifact_paths[1].read_text("utf-8"))
    ablation = json.loads(artifact_paths[2].read_text("utf-8"))
    with (submission / "results.csv").open(newline="", encoding="utf-8") as handle:
        csv_rows = list(csv.DictReader(handle))

    benchmark = results["deterministic_benchmark"]
    assert benchmark["fixture_counts"] == {
        "identities": 12,
        "records": 36,
        "cases": 21,
        "same_identity_cases": 12,
        "different_identity_cases": 8,
        "genuinely_ambiguous_cases": 1,
    }
    assert len(raw["cases"]) == 21
    assert {row["system_id"] for row in csv_rows} == {
        "fuzzy",
        "generic",
        "structured",
        "threadline",
    }
    judge = results["judge_case_comparison"]
    assert judge["same_input_verification"]["exact_input_shared"] is True
    assert judge["systems"]["threadline"]["workflow"]["contract_release_status"] == "withheld"
    assert "not model performance" in judge["evaluation_label"].lower()
    assert "—" not in judge["evaluation_label"]
    assert ablation["source_counterfactual"]["changed"] is True
    assert ablation["evidence_contract_node_ablation"]["status"] == "Not measured"
