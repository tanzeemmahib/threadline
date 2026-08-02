from __future__ import annotations

from uuid import uuid4

from app.benchmark.error_analysis import analyze_errors
from app.benchmark.metrics import metrics_by_id
from app.benchmark.runner import BenchmarkRunner
from app.schemas.models import (
    AblationConfigurationResult,
    AblationRunResponse,
    BenchmarkDataset,
    ProviderMode,
)
from app.workflow.registry import disableable_node_ids, workflow_nodes


class AblationRunner:
    def __init__(self, benchmark_runner: BenchmarkRunner) -> None:
        self.benchmark_runner = benchmark_runner

    async def run(
        self,
        dataset: BenchmarkDataset,
        *,
        mode: ProviderMode,
        selected_nodes: list[str],
    ) -> AblationRunResponse:
        invalid = set(selected_nodes) - disableable_node_ids()
        if invalid:
            raise ValueError(f"Unsupported ablation nodes: {sorted(invalid)}")
        full_outputs, full_metrics = await self.benchmark_runner.run_full_workflow(
            dataset, mode=mode, disabled_nodes=[]
        )
        full_errors = analyze_errors(
            dataset.ground_truth, full_outputs, workflow_configuration="full"
        )
        configurations: list[tuple[str, list[str]]] = [("full", [])]
        labels = {
            "normalize": "normalization",
            "adjudicate": "adjudication",
        }
        configurations.extend((f"no-{labels.get(node, node)}", [node]) for node in selected_nodes)
        if len(selected_nodes) > 1:
            configurations.append(("selected-combined", sorted(set(selected_nodes))))
        results: list[AblationConfigurationResult] = []
        full_values = metrics_by_id(full_metrics)
        full_error_keys = {(error.case_id, error.category) for error in full_errors}
        for configuration_id, disabled in configurations:
            if not disabled:
                outputs, metrics, errors = full_outputs, full_metrics, full_errors
            else:
                outputs, metrics = await self.benchmark_runner.run_full_workflow(
                    dataset, mode=mode, disabled_nodes=disabled
                )
                errors = analyze_errors(
                    dataset.ground_truth,
                    outputs,
                    workflow_configuration=configuration_id,
                )
            error_keys = {(error.case_id, error.category) for error in errors}
            results.append(
                AblationConfigurationResult(
                    configuration_id=configuration_id,
                    enabled_nodes=[
                        node.node_id for node in workflow_nodes() if node.node_id not in disabled
                    ],
                    disabled_nodes=disabled,
                    metrics=metrics,
                    changes_from_full={
                        key: round(value - full_values.get(key, 0), 3)
                        for key, value in metrics_by_id(metrics).items()
                    },
                    newly_introduced_errors=[
                        error
                        for error in errors
                        if (error.case_id, error.category) not in full_error_keys
                    ],
                    resolved_errors=[
                        error
                        for error in full_errors
                        if (error.case_id, error.category) not in error_keys
                    ],
                    affected_case_ids=sorted(
                        {
                            error.case_id
                            for error in [*errors, *full_errors]
                            if (error.case_id, error.category) in error_keys ^ full_error_keys
                        }
                    ),
                )
            )
        return AblationRunResponse(
            ablation_run_id=f"ABLATION-{uuid4()}",
            benchmark_id=dataset.benchmark_id,
            evaluation_mode=(
                "Deterministic mock evaluation"
                if mode == ProviderMode.mock
                else "Real-provider evaluation"
            ),
            configurations=results,
        )
