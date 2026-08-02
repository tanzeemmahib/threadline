from __future__ import annotations

from app.schemas.models import GroundTruthCase, RiskCoveragePoint, SystemOutput


def review_priority_score(output: SystemOutput) -> float:
    """Observable review workload score; deliberately not a calibrated probability."""
    candidate = output.output.get("candidate")
    score = 0.15
    if output.classification.value in {"insufficient_evidence", "conflicting_evidence"}:
        score += 0.25
    if isinstance(candidate, dict):
        score += min(0.2, len(candidate.get("conflicts", [])) * 0.08)
        score += min(0.2, len(candidate.get("rivals", [])) * 0.08)
        score += min(0.1, len(candidate.get("abstention_reasons", [])) * 0.04)
    if len(output.cited_evidence) < 2:
        score += 0.15
    return round(min(score, 1.0), 4)


def calculate_risk_coverage(
    ground_truth: list[GroundTruthCase], outputs: list[SystemOutput]
) -> list[RiskCoveragePoint]:
    expected = {case.case_id: case.expected_classification for case in ground_truth}
    policies: list[tuple[str, float]] = [
        ("exploratory", 0.75),
        ("balanced", 0.5),
        ("conservative", 0.25),
    ]
    points: list[RiskCoveragePoint] = []
    for policy, threshold in policies:
        automated = [item for item in outputs if review_priority_score(item) < threshold]
        errors = sum(
            item.case_id is None or item.classification != expected.get(item.case_id)
            for item in automated
        )
        total = len(outputs)
        points.append(
            RiskCoveragePoint(
                policy=policy,
                review_priority_threshold=threshold,
                coverage=round(len(automated) / total, 4) if total else 0,
                selective_risk=round(errors / len(automated), 4) if automated else 0,
                reviewed_cases=total - len(automated),
                total_cases=total,
            )
        )
    return points
