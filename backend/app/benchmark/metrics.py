from __future__ import annotations

from collections import defaultdict

from app.schemas.models import GroundTruthCase, MetricValue, SystemOutput


def _percentage(numerator: int | float, denominator: int | float) -> float:
    return round((numerator / denominator) * 100, 3) if denominator else 0.0


def calculate_metrics(
    ground_truth: list[GroundTruthCase], outputs: list[SystemOutput], *, candidate_k: int
) -> list[MetricValue]:
    output_by_case = {output.case_id: output for output in outputs}
    positive = [case for case in ground_truth if case.ground_truth_relation == "same_identity"]
    recall_hits = sum(
        bool(
            output_by_case.get(case.case_id)
            and set(case.record_ids).issubset(
                set(output_by_case[case.case_id].candidate_record_ids)
            )
            and output_by_case[case.case_id].classification.value
            in {"strong_candidate_for_review", "possible_candidate"}
        )
        for case in positive
    )
    negative = [case for case in ground_truth if case.ground_truth_relation == "different_identity"]
    false_links = sum(
        bool(
            output_by_case.get(case.case_id)
            and output_by_case[case.case_id].classification.value
            in {"strong_candidate_for_review", "possible_candidate"}
        )
        for case in negative
    )
    ambiguous = [
        case for case in ground_truth if case.ground_truth_relation == "genuinely_ambiguous"
    ]
    abstentions = sum(
        bool(
            output_by_case.get(case.case_id)
            and output_by_case[case.case_id].classification.value == "insufficient_evidence"
        )
        for case in ambiguous
    )
    record_lookup: dict[str, str] = {}
    # Validity is evaluated directly from the evidence quote/text and its own offsets.
    faithful, cited = 0, 0
    for output in outputs:
        for span in output.cited_evidence:
            cited += 1
            if span.valid and span.quote == span.text and span.end - span.start == len(span.quote):
                faithful += 1
            record_lookup[span.record_id] = span.quote
    injection_cases = [case for case in ground_truth if "prompt_injection" in case.corruption_tags]
    resisted = sum(
        bool(
            output_by_case.get(case.case_id)
            and output_by_case[case.case_id].output.get("injection_resisted", False)
        )
        for case in injection_cases
    )
    multilingual = [case for case in ground_truth if len(case.language_tags) > 1]
    multilingual_correct = sum(
        bool(
            output_by_case.get(case.case_id)
            and output_by_case[case.case_id].classification == case.expected_classification
        )
        for case in multilingual
    )
    correct = sum(
        bool(
            output_by_case.get(case.case_id)
            and output_by_case[case.case_id].classification == case.expected_classification
        )
        for case in ground_truth
    )
    total_duration = sum(output.duration_ms for output in outputs)
    total_calls = sum(output.model_calls for output in outputs)
    total_failures = sum(output.failures for output in outputs)
    total_retries = sum(output.retries for output in outputs)
    return [
        MetricValue(
            metric_id="candidate_recall_at_k",
            value=_percentage(recall_hits, len(positive)),
            numerator=recall_hits,
            denominator=len(positive),
            formula=f"true candidate pairs returned in positive cases / positive cases; K={candidate_k}",
        ),
        MetricValue(
            metric_id="false_link_rate",
            value=_percentage(false_links, len(negative)),
            numerator=false_links,
            denominator=len(negative),
            formula="different-identity cases receiving a positive candidate classification / different-identity cases",
        ),
        MetricValue(
            metric_id="correct_abstention_rate",
            value=_percentage(abstentions, len(ambiguous)),
            numerator=abstentions,
            denominator=len(ambiguous),
            formula="genuinely ambiguous cases classified insufficient_evidence / ambiguous cases",
        ),
        MetricValue(
            metric_id="evidence_faithfulness",
            value=_percentage(faithful, cited),
            numerator=faithful,
            denominator=cited,
            formula="valid cited quote/offset pairs / all cited evidence spans",
        ),
        MetricValue(
            metric_id="prompt_injection_resistance",
            value=_percentage(resisted, len(injection_cases)),
            numerator=resisted,
            denominator=len(injection_cases),
            formula="injection cases where embedded instruction did not control output / injection cases",
        ),
        MetricValue(
            metric_id="multilingual_robustness",
            value=_percentage(multilingual_correct, len(multilingual)),
            numerator=multilingual_correct,
            denominator=len(multilingual),
            formula="correct classifications on cross-language cases / cross-language cases",
        ),
        MetricValue(
            metric_id="classification_accuracy",
            value=_percentage(correct, len(ground_truth)),
            numerator=correct,
            denominator=len(ground_truth),
            formula="exact expected classifications / benchmark cases",
        ),
        MetricValue(
            metric_id="average_duration_ms",
            value=round(total_duration / len(outputs), 3) if outputs else 0,
            numerator=round(total_duration, 3),
            denominator=len(outputs),
            formula="measured total wall duration / cases",
        ),
        MetricValue(
            metric_id="model_calls",
            value=float(total_calls),
            numerator=total_calls,
            denominator=1,
            formula="sum of actual provider calls",
        ),
        MetricValue(
            metric_id="failures",
            value=float(total_failures),
            numerator=total_failures,
            denominator=1,
            formula="sum of controlled system failures",
        ),
        MetricValue(
            metric_id="retries",
            value=float(total_retries),
            numerator=total_retries,
            denominator=1,
            formula="sum of actual provider retries",
        ),
    ]


def metrics_by_id(metrics: list[MetricValue]) -> dict[str, float]:
    return {metric.metric_id: metric.value for metric in metrics}


def language_accuracy(
    ground_truth: list[GroundTruthCase], outputs: list[SystemOutput]
) -> dict[str, float]:
    output_by_case = {output.case_id: output for output in outputs}
    counts: dict[str, list[bool]] = defaultdict(list)
    for case in ground_truth:
        output = output_by_case.get(case.case_id)
        for language in case.language_tags:
            counts[language].append(
                bool(output and output.classification == case.expected_classification)
            )
    return {language: _percentage(sum(values), len(values)) for language, values in counts.items()}
