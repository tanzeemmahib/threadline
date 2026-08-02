from __future__ import annotations

from time import perf_counter

from app.baselines.fuzzy_matcher import run_fuzzy
from app.benchmark.metrics import calculate_metrics
from app.benchmark.runner import request_for_case
from app.config import Settings
from app.providers.base import ModelProvider
from app.schemas.models import (
    AdaptiveRouterComparison,
    BenchmarkDataset,
    Classification,
    ProviderMode,
    RouterDecision,
    SystemOutput,
)
from app.workflow.orchestrator import WorkflowOrchestrator


def _decision(dataset: BenchmarkDataset, case_id: str, record_ids: list[str]) -> RouterDecision:
    records = [item for item in dataset.records if item.record_id in set(record_ids)]
    joined = " ".join(item.text.lower() for item in records)
    signals: list[str] = []
    if len({item.language for item in records}) > 1:
        signals.append("multilingual_records")
    if "ignore previous" in joined or "mark this as confirmed" in joined:
        signals.append("instruction_like_text")
    if any(tag in joined for tag in ("unknown", "missing", "not recorded")):
        signals.append("missing_observable_fields")
    if any(tag in joined for tag in ("after a", "contradict", "impossible")):
        signals.append("timeline_or_conflict_language")
    if len(records) > 2:
        signals.append("multiple_rivals")
    if not signals and len(records) == 2:
        profile, disabled = "deterministic_only", []
    elif len(signals) <= 1 and "instruction_like_text" not in signals:
        profile, disabled = "reduced", ["rivals", "adjudicate"]
    else:
        profile, disabled = "full", []
    return RouterDecision(
        case_id=case_id,
        profile=profile,
        observable_signals=signals or ["low_observable_complexity"],
        disabled_nodes=disabled,
    )


async def compare_adaptive_router(
    dataset: BenchmarkDataset,
    full_outputs: list[SystemOutput],
    *,
    mode: ProviderMode,
    candidate_k: int,
    settings: Settings,
    provider: ModelProvider,  # type: ignore[type-arg]
) -> AdaptiveRouterComparison:
    adaptive: list[SystemOutput] = []
    decisions: list[RouterDecision] = []
    for case in dataset.ground_truth:
        decision = _decision(dataset, case.case_id, case.record_ids)
        decisions.append(decision)
        request = request_for_case(
            dataset,
            case,
            mode,
            candidate_k=candidate_k,
            disabled_nodes=decision.disabled_nodes,
        )
        if decision.profile == "deterministic_only":
            output = run_fuzzy(request)
            output.system_id = "threadline"
            output.system_name = "Adaptive THREADLINE router"
            output.case_id = case.case_id
            output.output["router_profile"] = decision.profile
            adaptive.append(output)
            continue
        started = perf_counter()
        response = await WorkflowOrchestrator(settings=settings, provider=provider).run(request)
        best = response.candidates[0] if response.candidates else None
        adaptive.append(
            SystemOutput(
                case_id=case.case_id,
                system_id="threadline",
                system_name="Adaptive THREADLINE router",
                evaluation_mode="Deterministic mock evaluation"
                if mode == ProviderMode.mock
                else "Real-provider evaluation",
                classification=best.classification_code
                if best
                else Classification.insufficient_evidence,
                candidate_record_ids=[best.record_a_id, best.record_b_id] if best else [],
                cited_evidence=[
                    span
                    for record in response.records
                    for span in record.evidence_spans
                    if span.valid
                ],
                output={
                    "candidate": best.model_dump(mode="json") if best else None,
                    "router_profile": decision.profile,
                    "disabled_nodes": decision.disabled_nodes,
                    "safety": "Candidate proposal only; authorized human review remains required.",
                },
                duration_ms=round((perf_counter() - started) * 1000, 3),
                model_calls=int(response.operational.get("model_calls", 0)),
                retries=int(response.operational.get("retries", 0)),
            )
        )
    return AdaptiveRouterComparison(
        decisions=decisions,
        full_metrics=calculate_metrics(dataset.ground_truth, full_outputs, candidate_k=candidate_k),
        adaptive_metrics=calculate_metrics(dataset.ground_truth, adaptive, candidate_k=candidate_k),
        full_model_calls=sum(item.model_calls for item in full_outputs),
        adaptive_model_calls=sum(item.model_calls for item in adaptive),
        full_duration_ms=round(sum(item.duration_ms for item in full_outputs), 3),
        adaptive_duration_ms=round(sum(item.duration_ms for item in adaptive), 3),
    )
