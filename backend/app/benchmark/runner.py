from __future__ import annotations

from collections import defaultdict
from collections.abc import Awaitable, Callable
from time import perf_counter
from uuid import uuid4

from app.baselines.runner import BaselineRunner
from app.benchmark.error_analysis import analyze_errors
from app.benchmark.metrics import calculate_metrics
from app.config import Settings
from app.providers.base import ModelProvider
from app.schemas.models import (
    AnalyzeOptions,
    AnalyzeRequest,
    BenchmarkDataset,
    BenchmarkRunResponse,
    BenchmarkSystemResult,
    Classification,
    GroundTruthCase,
    IncidentInput,
    MetricValue,
    ProviderMode,
    RecordInput,
    SystemOutput,
)
from app.workflow.orchestrator import WorkflowOrchestrator


def request_for_case(
    dataset: BenchmarkDataset,
    case: GroundTruthCase,
    mode: ProviderMode,
    *,
    candidate_k: int,
    disabled_nodes: list[str] | None = None,
) -> AnalyzeRequest:
    wanted = set(case.record_ids)
    records = [
        RecordInput.model_validate(
            record.model_dump(
                include={
                    "record_id",
                    "source_type",
                    "language",
                    "text",
                    "timestamp",
                    "display_name",
                    "source_reliability_metadata",
                    "translated_text",
                }
            )
        )
        for record in dataset.records
        if record.record_id in wanted
    ]
    return AnalyzeRequest(
        incident=IncidentInput(
            incident_id=f"INCIDENT-{dataset.benchmark_id}",
            name="Deterministic synthetic benchmark incident",
            languages=dataset.configuration.languages,
            description="Synthetic identities only.",
        ),
        records=records,
        options=AnalyzeOptions(
            provider_mode=mode,
            candidate_limit=min(candidate_k, 10),
            disabled_nodes=disabled_nodes or [],
        ),
    )


class BenchmarkRunner:
    def __init__(self, *, settings: Settings, provider: ModelProvider) -> None:  # type: ignore[type-arg]
        self.settings = settings
        self.provider = provider

    async def run(
        self,
        dataset: BenchmarkDataset,
        *,
        mode: ProviderMode,
        candidate_k: int,
        progress_callback: Callable[[int, int, str], Awaitable[None]] | None = None,
    ) -> BenchmarkRunResponse:
        outputs_by_system: dict[str, list[SystemOutput]] = defaultdict(list)
        names: dict[str, str] = {}
        total_cases = len(dataset.ground_truth)
        for case_index, case in enumerate(dataset.ground_truth, start=1):
            request = request_for_case(dataset, case, mode, candidate_k=candidate_k)
            comparison = await BaselineRunner(settings=self.settings, provider=self.provider).run(
                request
            )
            for output in comparison.systems:
                output.case_id = case.case_id
                outputs_by_system[output.system_id].append(output)
                names[output.system_id] = output.system_name
            if progress_callback is not None:
                await progress_callback(case_index, total_cases, f"benchmark:{case.case_id}")
        evaluation_mode = (
            "Deterministic mock evaluation"
            if mode == ProviderMode.mock
            else "Real-provider evaluation"
        )
        systems = []
        for system_id in ("fuzzy", "generic", "structured", "threadline"):
            outputs = outputs_by_system[system_id]
            systems.append(
                BenchmarkSystemResult(
                    system_id=system_id,
                    system_name=names[system_id],
                    evaluation_mode=evaluation_mode,
                    metrics=calculate_metrics(
                        dataset.ground_truth, outputs, candidate_k=candidate_k
                    ),
                    outputs=outputs,
                    errors=analyze_errors(
                        dataset.ground_truth, outputs, workflow_configuration="full"
                    ),
                    operational={
                        "cases": len(outputs),
                        "measured_duration_ms": round(
                            sum(output.duration_ms for output in outputs), 3
                        ),
                        "model_calls": sum(output.model_calls for output in outputs),
                        "failures": sum(output.failures for output in outputs),
                        "retries": sum(output.retries for output in outputs),
                    },
                )
            )
        return BenchmarkRunResponse(
            benchmark_run_id=f"BENCH-RUN-{uuid4()}",
            benchmark_id=dataset.benchmark_id,
            evaluation_mode=evaluation_mode,
            systems=systems,
        )

    async def run_full_workflow(
        self,
        dataset: BenchmarkDataset,
        *,
        mode: ProviderMode,
        disabled_nodes: list[str],
        candidate_k: int = 5,
    ) -> tuple[list[SystemOutput], list[MetricValue]]:
        outputs: list[SystemOutput] = []
        for case in dataset.ground_truth:
            request = request_for_case(
                dataset,
                case,
                mode,
                candidate_k=candidate_k,
                disabled_nodes=disabled_nodes,
            )
            started = perf_counter()
            response = await WorkflowOrchestrator(
                settings=self.settings, provider=self.provider
            ).run(request)
            best = response.candidates[0] if response.candidates else None
            outputs.append(
                SystemOutput(
                    case_id=case.case_id,
                    system_id="threadline",
                    system_name="Full THREADLINE workflow",
                    evaluation_mode=(
                        "Deterministic mock evaluation"
                        if mode == ProviderMode.mock
                        else "Real-provider evaluation"
                    ),
                    classification=(
                        best.classification_code if best else Classification.insufficient_evidence
                    ),
                    candidate_record_ids=([best.record_a_id, best.record_b_id] if best else []),
                    cited_evidence=[
                        span
                        for record in response.records
                        for span in record.evidence_spans
                        if span.valid
                    ],
                    output={
                        "candidate": best.model_dump(mode="json") if best else None,
                        "injection_resisted": (
                            "quarantine" not in disabled_nodes
                            and all(
                                record.quarantined
                                for record in response.records
                                if record.detected_instructions
                            )
                        ),
                        "disabled_nodes": disabled_nodes,
                    },
                    duration_ms=round((perf_counter() - started) * 1000, 3),
                    model_calls=int(response.operational.get("model_calls", 0)),
                    retries=int(response.operational.get("retries", 0)),
                )
            )
        metrics = calculate_metrics(dataset.ground_truth, outputs, candidate_k=candidate_k)
        return outputs, metrics
