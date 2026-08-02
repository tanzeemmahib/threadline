from app.benchmark.generator import generate_benchmark
from app.benchmark.metrics import calculate_metrics
from app.schemas.models import BenchmarkConfig, Classification, SystemOutput


def test_benchmark_generation_is_deterministic() -> None:
    config = BenchmarkConfig(seed=91, identities=3, records_per_identity=2)
    first = generate_benchmark(config)
    second = generate_benchmark(config)
    assert first.content_hash == second.content_hash
    assert first.model_dump(mode="json") == second.model_dump(mode="json")
    assert any(case.ground_truth_relation == "genuinely_ambiguous" for case in first.ground_truth)


def test_metrics_are_calculated_from_outputs() -> None:
    dataset = generate_benchmark(BenchmarkConfig(seed=5, identities=3, records_per_identity=2))
    outputs = [
        SystemOutput(
            case_id=case.case_id,
            system_id="fuzzy",
            system_name="Test",
            evaluation_mode="Deterministic mock evaluation",
            classification=case.expected_classification,
            candidate_record_ids=case.record_ids,
            cited_evidence=[],
            output={"injection_resisted": True},
            duration_ms=1,
            model_calls=0,
        )
        for case in dataset.ground_truth
    ]
    metrics = {
        item.metric_id: item
        for item in calculate_metrics(dataset.ground_truth, outputs, candidate_k=5)
    }
    assert metrics["classification_accuracy"].value == 100
    assert metrics["classification_accuracy"].numerator == len(dataset.ground_truth)
    assert metrics["average_duration_ms"].value == 1


def test_metric_changes_when_output_changes() -> None:
    dataset = generate_benchmark(BenchmarkConfig(seed=7, identities=3, records_per_identity=2))
    case = dataset.ground_truth[0]
    output = SystemOutput(
        case_id=case.case_id,
        system_id="fuzzy",
        system_name="Test",
        evaluation_mode="Deterministic mock evaluation",
        classification=Classification.insufficient_evidence,
        candidate_record_ids=[],
        cited_evidence=[],
        output={},
        duration_ms=0,
        model_calls=0,
    )
    metrics = {
        item.metric_id: item.value for item in calculate_metrics([case], [output], candidate_k=5)
    }
    assert metrics["candidate_recall_at_k"] == 0
