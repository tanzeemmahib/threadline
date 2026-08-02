from __future__ import annotations

from app.schemas.models import ErrorAnalysisCase, GroundTruthCase, SystemOutput


def analyze_errors(
    ground_truth: list[GroundTruthCase],
    outputs: list[SystemOutput],
    *,
    workflow_configuration: str,
) -> list[ErrorAnalysisCase]:
    output_by_case = {output.case_id: output for output in outputs}
    errors: list[ErrorAnalysisCase] = []
    for case in ground_truth:
        output = output_by_case.get(case.case_id)
        if output is None or output.classification == case.expected_classification:
            continue
        actual = output.classification.value if output else "system_failure"
        category = "extraction_error"
        node = "extract"
        severity = "high"
        if case.ground_truth_relation == "same_identity" and actual == "insufficient_evidence":
            category, node = "missed_true_candidate", "retrieve"
        elif case.ground_truth_relation == "different_identity" and actual in {
            "strong_candidate_for_review",
            "possible_candidate",
        }:
            category, node, severity = "incorrect_candidate_link", "prosecutor", "critical"
        elif case.ground_truth_relation == "genuinely_ambiguous":
            category, node = "failed_abstention", "rivals"
        elif "transliteration_variant" in case.corruption_tags:
            category, node = "transliteration_failure", "normalize"
        elif "contradictory_timestamp" in case.corruption_tags:
            category, node = "timeline_reasoning_failure", "timeline"
        elif "prompt_injection" in case.corruption_tags:
            category, node, severity = "prompt_injection_failure", "quarantine", "critical"
        errors.append(
            ErrorAnalysisCase(
                error_id=f"ERR-{len(errors) + 1:04d}",
                case_id=case.case_id,
                category=category,
                record_ids=case.record_ids,
                expected_result=case.expected_classification.value,
                actual_result=actual,
                system=output.system_id if output else "unknown",
                workflow_configuration=workflow_configuration,
                first_divergent_node=node,
                evidence=case.expected_evidence_fields,
                severity=severity,
                suggested_investigation=f"Inspect the {node} trace and cited source spans for this synthetic case.",
            )
        )
    return errors
