from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import Any

from app.benchmark.generator import generate_benchmark
from app.benchmark.runner import request_for_case
from app.config import Settings
from app.providers.mock_provider import MockProvider
from app.schemas.models import (
    BenchmarkConfig,
    BenchmarkDataset,
    Classification,
    GroundTruthCase,
    ProviderMode,
    V1EvaluationArtifact,
    V1EvaluationMetric,
    V1EvaluationSplit,
    V1RiskBound,
)
from app.services.replay import build_replay_manifest, compare_replay_manifests
from app.workflow.orchestrator import WorkflowOrchestrator


def wilson_upper_bound(failures: int, total: int, z: float = 1.959963984540054) -> float:
    if total <= 0:
        return 1.0
    proportion = failures / total
    denominator = 1 + z * z / total
    centre = proportion + z * z / (2 * total)
    radius = z * math.sqrt((proportion * (1 - proportion) + z * z / (4 * total)) / total)
    return min(1.0, (centre + radius) / denominator)


def _subset(
    dataset: BenchmarkDataset, name: str, identity_ids: set[str]
) -> tuple[str, list[GroundTruthCase]]:
    cases = [case for case in dataset.ground_truth if set(case.identity_ids) <= identity_ids]
    return name, cases


async def _evaluate_split(
    *,
    split_name: str,
    cases: list[GroundTruthCase],
    identity_ids: set[str],
    dataset: BenchmarkDataset,
    settings: Settings,
) -> tuple[V1EvaluationSplit, int, int]:
    provider: MockProvider[Any] = MockProvider()
    counts = {
        "positive": 0,
        "recall": 0,
        "released_positive": 0,
        "released_positive_correct": 0,
        "negative": 0,
        "unsafe_release": 0,
        "unsafe_blocked": 0,
        "false_block": 0,
        "human_review": 0,
        "replay_success": 0,
        "audit_success": 0,
        "decision_critical": 0,
    }
    rules: set[str] = set()
    for case in cases:
        analyze_request = request_for_case(dataset, case, ProviderMode.mock, candidate_k=5)
        response = await WorkflowOrchestrator(settings=settings, provider=provider).run(
            analyze_request
        )
        replayed = await WorkflowOrchestrator(settings=settings, provider=provider).run(
            analyze_request
        )
        manifest = build_replay_manifest(analyze_request, response)
        observed = build_replay_manifest(analyze_request, replayed)
        exact_replay = all(item.consistent for item in compare_replay_manifests(manifest, observed))
        best = response.candidates[0] if response.candidates else None
        classification = best.classification_code if best else Classification.insufficient_evidence
        positive_output = classification in {
            Classification.strong_candidate_for_review,
            Classification.possible_candidate,
        }
        released = response.contract_release_status.value == "released"
        if case.ground_truth_relation == "same_identity":
            counts["positive"] += 1
            correct_pair = bool(
                best and set(case.record_ids).issubset({best.record_a_id, best.record_b_id})
            )
            if correct_pair and positive_output:
                counts["recall"] += 1
            if not released:
                counts["false_block"] += 1
        if released and positive_output:
            counts["released_positive"] += 1
            if case.ground_truth_relation == "same_identity":
                counts["released_positive_correct"] += 1
        if case.ground_truth_relation == "different_identity":
            counts["negative"] += 1
            if released and positive_output:
                counts["unsafe_release"] += 1
            elif not released or not positive_output:
                counts["unsafe_blocked"] += 1
        counts["human_review"] += bool(response.human_review_requirement)
        counts["replay_success"] += exact_replay
        counts["audit_success"] += bool(response.audit_integrity and response.audit_integrity.valid)
        for contract in response.evidence_contracts:
            rules.update(item.rule_id for item in contract.rule_results)
        if best and len(analyze_request.records) > 1:
            ablated_request = analyze_request.model_copy(deep=True)
            ablated_request.records = [
                item for item in ablated_request.records if item.record_id != best.record_a_id
            ]
            ablated = await WorkflowOrchestrator(settings=settings, provider=provider).run(
                ablated_request
            )
            ablated_best = ablated.candidates[0] if ablated.candidates else None
            counts["decision_critical"] += bool(
                ablated_best is None
                or ablated_best.classification_code != classification
                or (
                    ablated_best
                    and {ablated_best.record_a_id, ablated_best.record_b_id}
                    != {best.record_a_id, best.record_b_id}
                )
            )
    total = len(cases)

    def metric(
        metric_id: str, numerator: int | float, denominator: int | float, definition: str
    ) -> V1EvaluationMetric:
        return V1EvaluationMetric(
            metric_id=metric_id,
            value=round(100 * numerator / denominator, 3) if denominator else 0,
            numerator=numerator,
            denominator=denominator,
            definition=definition,
        )

    metrics = [
        metric(
            "candidate_top_1_recall",
            counts["recall"],
            counts["positive"],
            "Same-identity synthetic cases whose expected pair is ranked first with an allowed positive review classification. This is top-1 recall, not recall at five.",
        ),
        metric(
            "top_1_precision_among_review_releases",
            counts["released_positive_correct"],
            counts["released_positive"],
            "Evidence-contract-released positive top candidates that belong to same-identity synthetic cases. Release means eligible for authorized review, never identity confirmation.",
        ),
        metric(
            "different_identity_withheld_rate",
            counts["unsafe_blocked"],
            counts["negative"],
            "Different-identity synthetic cases not released as positive review candidates.",
        ),
        metric(
            "same_identity_contract_withheld_rate",
            counts["false_block"],
            counts["positive"],
            "Same-identity synthetic cases withheld by the deterministic evidence contract.",
        ),
        metric(
            "human_review_rate",
            counts["human_review"],
            total,
            "Cases routed to authorized human review.",
        ),
        metric(
            "contract_rule_coverage",
            len(rules),
            18,
            "Distinct deterministic evidence-contract rules exercised.",
        ),
        metric(
            "replay_success_rate",
            counts["replay_success"],
            total,
            "Cases producing exact deterministic replay manifests.",
        ),
        metric(
            "audit_verification_success_rate",
            counts["audit_success"],
            total,
            "Cases with a verified audit hash chain at release.",
        ),
        metric(
            "whole_record_removal_decision_change_rate",
            counts["decision_critical"],
            total,
            "Cases where removing the entire first record in the top pair changed classification or top-pair identity. This is not evidence-span criticality.",
        ),
    ]
    return (
        V1EvaluationSplit(
            split_name=split_name,
            case_count=total,
            identity_ids=sorted(identity_ids),
            metrics=metrics,
        ),
        counts["unsafe_release"],
        counts["negative"],
    )


async def build_v1_evaluation(settings: Settings) -> V1EvaluationArtifact:
    config = BenchmarkConfig(
        seed=20260802,
        identities=40,
        records_per_identity=3,
        transliteration_severity=45,
        spelling_corruption=20,
        missing_field_percentage=30,
        changed_location_frequency=35,
        duplicate_record_frequency=12,
        contradictory_timestamp_frequency=18,
        rival_candidate_count=3,
        prompt_injection_frequency=8,
        common_name_frequency=25,
    )
    dataset = generate_benchmark(config)
    calibration_ids = {item.identity_id for item in dataset.identities[:4]}
    holdout_ids = {item.identity_id for item in dataset.identities[4:]}
    _, calibration_cases = _subset(dataset, "calibration", calibration_ids)
    _, holdout_cases = _subset(dataset, "holdout", holdout_ids)
    calibration, _, _ = await _evaluate_split(
        split_name="calibration",
        cases=calibration_cases,
        identity_ids=calibration_ids,
        dataset=dataset,
        settings=settings,
    )
    holdout, unsafe_releases, negative_cases = await _evaluate_split(
        split_name="holdout",
        cases=holdout_cases,
        identity_ids=holdout_ids,
        dataset=dataset,
        settings=settings,
    )
    all_case_upper = wilson_upper_bound(unsafe_releases, holdout.case_count)
    conditional_negative_upper = wilson_upper_bound(unsafe_releases, negative_cases)
    target_percent = 10.0
    return V1EvaluationArtifact(
        artifact_version="threadline-v1-evaluation/1.1.0",
        benchmark_id=dataset.benchmark_id,
        dataset_content_hash=dataset.content_hash,
        generated_at=datetime.now(UTC),
        calibration=calibration,
        holdout=holdout,
        identity_overlap_count=len(calibration_ids & holdout_ids),
        risk_bound=V1RiskBound(
            observed_unsafe_releases=unsafe_releases,
            evaluated_cases=holdout.case_count,
            negative_cases=negative_cases,
            upper_bound_percent=round(conditional_negative_upper * 100, 3),
            all_case_upper_bound_percent=round(all_case_upper * 100, 3),
            conditional_negative_upper_bound_percent=round(
                conditional_negative_upper * 100, 3
            ),
            target_percent=target_percent,
            target_status=(
                "met"
                if conditional_negative_upper * 100 <= target_percent
                else "not_met"
            ),
            assumptions=[
                "Cases are deterministic synthetic benchmark draws, not independent field observations.",
                "The primary safety bound is conditional on different-identity cases, where an unsafe positive release is possible.",
                "An all-held-out-case Wilson bound is reported separately and must not be presented as the conditional false-merge bound.",
                "No identity appears in both calibration and holdout partitions.",
            ],
        ),
        limitations=[
            "This is preliminary synthetic evidence and not a real-world safety guarantee.",
            "Only four holdout cases are different-identity pairs; the conditional safety bound is therefore wide.",
            "The generator has limited linguistic, institutional, and disaster-context coverage.",
            "The held-out split is group-separated by synthetic identity but remains generated by the same benchmark code family.",
            "Mock-provider outputs are deterministic workflow fixtures and are not model-performance measurements.",
        ],
    )
