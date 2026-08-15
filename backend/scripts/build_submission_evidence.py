"""Build the locked, judge-facing THREADLINE submission evidence artifacts.

The generated benchmark comparison uses the deterministic mock provider. It is
useful for comparing workflow behavior on identical inputs, but it is explicitly
not a model-performance evaluation. The archived live-provider extraction run is
reported as a separate evidence track and is never blended with mock results.
"""

from __future__ import annotations

import asyncio
import csv
import hashlib
import json
import math
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.baselines.runner import BaselineRunner
from app.baselines.single_call import build_input_manifest
from app.benchmark.ablation import AblationRunner
from app.benchmark.generator import generate_benchmark
from app.benchmark.runner import BenchmarkRunner, request_for_case
from app.config import Settings
from app.prompts import load_prompt
from app.providers.mock_provider import MockProvider
from app.schemas.models import BenchmarkConfig, ProviderMode, SystemOutput
from app.v1_demo import v1_analyze_request

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = BACKEND_ROOT.parent
DEFAULT_OUTPUT_DIR = REPOSITORY_ROOT / "docs" / "submission"
DETERMINISTIC_LABEL = "Deterministic mock replay - not model performance."
LIVE_LABEL = "Archived measured live-provider extraction run (one run)."
SUBMISSION_SYSTEM_NAMES = {
    "generic": "Generic single-prompt baseline",
    "structured": "Structured single-call baseline",
}

BENCHMARK_CONFIG = BenchmarkConfig(
    seed=41027,
    identities=12,
    records_per_identity=3,
    languages=["English", "Arabic", "French"],
    transliteration_severity=35,
    spelling_corruption=12,
    missing_field_percentage=24,
    estimated_age_variance=2,
    changed_location_frequency=30,
    duplicate_record_frequency=8,
    contradictory_timestamp_frequency=10,
    rival_candidate_count=2,
    prompt_injection_frequency=5,
    common_name_frequency=18,
)


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _git_state() -> dict[str, str | bool]:
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=REPOSITORY_ROOT,
            text=True,
        ).strip()
        dirty = bool(
            subprocess.check_output(
                ["git", "status", "--porcelain"],
                cwd=REPOSITORY_ROOT,
                text=True,
            ).strip()
        )
        return {"commit": commit, "working_tree_dirty": dirty}
    except (OSError, subprocess.CalledProcessError):
        return {"commit": "Not available", "working_tree_dirty": True}


def _metric_rows(system: Any) -> list[dict[str, Any]]:
    return [
        {
            "metric_id": metric.metric_id,
            "value": metric.value,
            "numerator": metric.numerator,
            "denominator": metric.denominator,
            "formula": metric.formula,
        }
        for metric in system.metrics
    ]


def _citation_rows(output: SystemOutput) -> list[dict[str, Any]]:
    return [
        {
            "span_id": span.span_id,
            "record_id": span.record_id,
            "field": span.field,
            "quote": span.quote,
            "start": span.start,
            "end": span.end,
            "valid": span.valid,
        }
        for span in output.cited_evidence
    ]


def _stable_system_output(output: SystemOutput) -> dict[str, Any]:
    selected_output: dict[str, Any] = {
        key: output.output[key]
        for key in (
            "ranking_score",
            "ranking_signal_only",
            "classification",
            "candidate_record_ids",
            "cited_evidence_span_ids",
            "supporting_evidence",
            "contradictions",
            "uncertainty",
            "injection_resisted",
            "prompt_template_id",
            "prompt_template_version",
            "provider_mode",
            "provider_model",
            "input_manifest",
            "evaluation_warning",
            "disabled_nodes",
        )
        if key in output.output
    }
    candidate = output.output.get("candidate")
    if isinstance(candidate, dict):
        selected_output["candidate"] = {
            key: candidate.get(key)
            for key in (
                "candidate_id",
                "record_a_id",
                "record_b_id",
                "label",
                "classification_code",
                "conflicts",
                "rivals",
            )
        }
    return {
        "system_id": output.system_id,
        "system_name": SUBMISSION_SYSTEM_NAMES.get(output.system_id, output.system_name),
        "evaluation_mode": output.evaluation_mode,
        "classification": output.classification.value,
        "candidate_record_ids": output.candidate_record_ids,
        "citations": _citation_rows(output),
        "output": selected_output,
        "model_calls": output.model_calls,
        "failures": output.failures,
        "retries": output.retries,
    }


def _contract_summary(workflow: dict[str, Any]) -> dict[str, Any]:
    contracts: list[dict[str, Any]] = []
    for contract in workflow.get("evidence_contracts", []):
        nonpassing = [
            {
                "rule_id": rule.get("rule_id"),
                "status": rule.get("status"),
                "reason_code": rule.get("reason_code"),
                "severity": rule.get("severity"),
                "affected_evidence_span_ids": rule.get("affected_evidence_span_ids", []),
            }
            for rule in contract.get("rule_results", [])
            if rule.get("status") != "pass"
        ]
        contracts.append(
            {
                "candidate_id": contract.get("candidate_id"),
                "contract_status": contract.get("contract_status"),
                "release_allowed_for_authorized_review": contract.get("release_allowed"),
                "nonpassing_rules": nonpassing,
            }
        )
    candidates = [
        {
            "candidate_id": candidate.get("candidate_id"),
            "record_ids": [candidate.get("record_a_id"), candidate.get("record_b_id")],
            "label": candidate.get("label"),
            "classification": candidate.get("classification_code"),
            "conflicts": [
                {
                    "field": conflict.get("field"),
                    "severity": conflict.get("severity"),
                    "explanation": conflict.get("explanation"),
                    "evidence_span_ids": conflict.get("evidence_span_ids", []),
                }
                for conflict in candidate.get("conflicts", [])
            ],
            "rivals": [
                {
                    "record_id": rival.get("record_id"),
                    "summary": rival.get("summary"),
                }
                for rival in candidate.get("rivals", [])
            ],
        }
        for candidate in workflow.get("candidates", [])
    ]
    return {
        "contract_release_status": workflow.get("contract_release_status"),
        "release_state": workflow.get("release_state"),
        "human_review_required": bool(workflow.get("human_review_requirement")),
        "contracts": contracts,
        "candidates": candidates,
    }


def _judge_system_summary(output: SystemOutput) -> dict[str, Any]:
    summary = _stable_system_output(output)
    if output.system_id == "threadline":
        workflow = output.output.get("workflow_response", {})
        summary["workflow"] = _contract_summary(workflow)
    return summary


def _judge_case_records(scenario: str) -> dict[str, Any]:
    request = v1_analyze_request(scenario)  # type: ignore[arg-type]
    return {
        "case_id": request.incident.incident_id,
        "scenario": scenario,
        "input_manifest": build_input_manifest(request),
        "records": [
            {
                "record_id": record.record_id,
                "source_type": record.source_type,
                "language": record.language,
                "text": record.text,
            }
            for record in request.records
        ],
    }


async def _judge_comparison(
    settings: Settings, provider: MockProvider[Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    runner = BaselineRunner(settings=settings, provider=provider)
    rival_request = v1_analyze_request("rival")
    passing_request = v1_analyze_request("passing")
    rival = await runner.run(rival_request)
    passing = await runner.run(passing_request)
    rival_outputs = {item.system_id: item for item in rival.systems}
    passing_outputs = {item.system_id: item for item in passing.systems}
    compared_ids = ("generic", "structured", "threadline")
    rival_hashes = {
        system_id: rival_outputs[system_id].output["input_manifest"]["input_sha256"]
        for system_id in compared_ids
    }
    rival_evidence_hashes = {
        system_id: rival_outputs[system_id].output["input_manifest"][
            "available_evidence_sha256"
        ]
        for system_id in compared_ids
    }
    exact_input_shared = len(set(rival_hashes.values())) == 1
    prompt_rows: dict[str, Any] = {}
    for template_id in ("generic_baseline", "structured_baseline"):
        template = load_prompt(template_id)
        prompt_rows[template_id] = {
            "template_id": template.template_id,
            "version": template.version,
            "sha256": _sha256_bytes(template.content.encode("utf-8")),
            "content": template.content,
        }
    comparison = {
        "artifact_id": "THREADLINE-JUDGE-CASE-V1-RIVAL",
        "synthetic_only": True,
        "evaluation_label": DETERMINISTIC_LABEL,
        "case": _judge_case_records("rival"),
        "same_input_verification": {
            "exact_input_shared": exact_input_shared,
            "input_sha256_by_system": rival_hashes,
            "available_evidence_sha256_by_system": rival_evidence_hashes,
            "record_ids_by_system": {
                system_id: rival_outputs[system_id].output["input_manifest"]["record_ids"]
                for system_id in compared_ids
            },
        },
        "provider": {
            "mode": provider.mode,
            "model": provider.model_name,
            "temperature": 0.0,
            "warning": DETERMINISTIC_LABEL,
        },
        "prompts": prompt_rows,
        "systems": {
            system_id: _judge_system_summary(rival_outputs[system_id])
            for system_id in compared_ids
        },
        "safe_conclusion": (
            "The deterministic one-call fixtures produced a plausible review candidate. "
            "The full workflow preserved the rival age contradiction and withheld aggregate "
            "release. This demonstrates code-path behavior, not model quality or identity."
        ),
    }
    rival_workflow = _contract_summary(
        rival_outputs["threadline"].output["workflow_response"]
    )
    passing_workflow = _contract_summary(
        passing_outputs["threadline"].output["workflow_response"]
    )
    counterfactual = {
        "counterfactual_id": "THREADLINE-V1-REMOVE-CONFLICTING-RIVAL",
        "type": "remove_source_record",
        "removed_record_id": "HOSPITAL-052",
        "before": {
            "case": _judge_case_records("rival"),
            "workflow": rival_workflow,
        },
        "after": {
            "case": _judge_case_records("passing"),
            "workflow": passing_workflow,
        },
        "changed": (
            rival_workflow["contract_release_status"]
            != passing_workflow["contract_release_status"]
        ),
        "rule_delta": {
            "removed_blocking_rule_names": [
                "TIMELINE_CONSISTENCY",
                "MATERIAL_CONTRADICTIONS_RESOLVED",
            ],
            "removed_conflict_field": "age",
            "affected_evidence_span_ids": [
                "SPAN-FAMILY-018-AGE-37",
                "SPAN-HOSPITAL-052-AGE-36",
                "SPAN-SHELTER-204-AGE-35",
            ],
        },
        "interpretation": (
            "Removing the contradictory hospital source changes which contract rules block "
            "authorized-review release. It does not prove that the remaining records describe "
            "the same person."
        ),
    }
    return comparison, counterfactual


def _archived_live_v2() -> dict[str, Any]:
    artifact_path = (
        BACKEND_ROOT
        / "data"
        / "live_runs_phase11"
        / "full-prompt-v2-run-1"
        / "live-artifact.json"
    )
    raw_path = artifact_path.with_name("raw-outputs.json")
    artifact = json.loads(artifact_path.read_text("utf-8"))
    raw = json.loads(raw_path.read_text("utf-8"))
    rows = list(raw["records"].values())
    successful = [row for row in rows if row["status"] == "ok"]
    latencies = sorted(float(row["latency_ms"]) for row in successful)
    middle = len(latencies) // 2
    median = (
        latencies[middle]
        if len(latencies) % 2
        else (latencies[middle - 1] + latencies[middle]) / 2
    )
    p95 = latencies[math.ceil(0.95 * len(latencies)) - 1]
    return {
        "artifact_id": "THREADLINE-LIVE-PROMPT-V2-FULL-RUN-1",
        "evaluation_label": LIVE_LABEL,
        "execution_mode": artifact["execution_mode"],
        "run_id": artifact["run_id"],
        "run_timestamp_utc": datetime.fromtimestamp(
            artifact["timestamp"], tz=UTC
        ).isoformat(),
        "provider": artifact["provider"],
        "model": artifact["model"],
        "temperature": artifact["temperature"],
        "prompt_version": artifact["prompt_version"],
        "fixture_sha256": artifact["fixture_sha256"],
        "ground_truth_schema": artifact["ground_truth_schema"],
        "identity_assignment_sha256": artifact["identity_assignment_sha256"],
        "source_files": {
            str(artifact_path.relative_to(REPOSITORY_ROOT)).replace("\\", "/"): _sha256_file(
                artifact_path
            ),
            str(raw_path.relative_to(REPOSITORY_ROOT)).replace("\\", "/"): _sha256_file(
                raw_path
            ),
        },
        "extraction_quality": artifact["extraction_quality"],
        "decision_metrics": artifact["metrics"],
        "retrieval": artifact["retrieval"],
        "safety": artifact["safety"],
        "operational": {
            "records": len(rows),
            "successful_records": len(successful),
            "failed_records": len(rows) - len(successful),
            "median_latency_ms": median,
            "p95_latency_ms": p95,
            "latency_population": "57 successful extraction calls",
            "p95_method": "nearest-rank (ceil(0.95 * n))",
            "total_tokens_successful_records": sum(
                int(row["tokens"]) for row in successful if row["tokens"] is not None
            ),
            "total_attempts": sum(int(row["attempts"]) for row in rows),
            "approximate_api_cost": "Not measured",
            "cost_note": (
                "The archive does not pin separate input/output token counts and a dated "
                "provider price table, so cost is not reconstructed."
            ),
        },
        "limitations": [
            "One archived live-provider run; no repeated-run confidence interval.",
            "This evaluates live extraction followed by deterministic policy, not a same-model single-prompt baseline comparison.",
            "Synthetic records only; no operational humanitarian validation.",
        ],
    }


def _report_markdown(results: dict[str, Any], ablation: dict[str, Any]) -> str:
    systems = results["deterministic_benchmark"]["systems"]
    metric_ids = ("candidate_recall_at_k", "false_link_rate", "correct_abstention_rate")
    lookup = {
        system["system_id"]: {metric["metric_id"]: metric for metric in system["metrics"]}
        for system in systems
    }
    lines = [
        "# THREADLINE submission benchmark report",
        "",
        "## Answer first",
        "",
        (
            "On the fixed deterministic 21-case harness, the generic and structured one-call "
            "fixtures returned a positive review candidate in all 8 different-identity cases; "
            "the full THREADLINE workflow returned none and abstained on the one deliberately "
            "ambiguous case. This is a workflow-behavior replay, **not model performance**."
        ),
        "",
        "## Deterministic same-case comparison",
        "",
        f"Evaluation label: **{DETERMINISTIC_LABEL}**",
        "",
        "| System | Candidate recall | False-link rate | Correct abstention |",
        "| --- | ---: | ---: | ---: |",
    ]
    for system in systems:
        values = lookup[system["system_id"]]
        cells = []
        for metric_id in metric_ids:
            metric = values[metric_id]
            cells.append(
                f"{metric['value']:.3f}% ({metric['numerator']}/{metric['denominator']})"
            )
        lines.append(f"| {system['system_name']} | {' | '.join(cells)} |")
    live = results["archived_live_prompt_v2"]
    lines.extend(
        [
            "",
            "## Archived live-provider evidence (separate track)",
            "",
            f"Evaluation label: **{LIVE_LABEL}**",
            "",
            "- Synthetic records: 58",
            "- Successful extractions: 57/58",
            f"- Extraction TP / FP / FN: {live['extraction_quality']['total_tp']} / {live['extraction_quality']['total_fp']} / {live['extraction_quality']['total_fn']}",
            f"- Extraction precision / recall / F1: {live['extraction_quality']['micro_precision']:.4f} / {live['extraction_quality']['micro_recall']:.4f} / {live['extraction_quality']['micro_f1']:.4f}",
            f"- Candidate retrieval: {live['retrieval']['d']}/{live['retrieval']['n']}",
            f"- True links / false merges / false non-links: {live['decision_metrics']['true_link_count']} / {live['decision_metrics']['false_merge_count']} / {live['decision_metrics']['false_non_match_count']}",
            f"- Median / p95 extraction latency: {live['operational']['median_latency_ms']:.0f} ms / {live['operational']['p95_latency_ms']:.0f} ms",
            "- Approximate API cost: Not measured",
            "",
            "## Ablation and counterfactual",
            "",
        ]
    )
    for configuration in ablation["benchmark_ablations"]["configurations"]:
        lines.append(
            f"- `{configuration['configuration_id']}`: "
            f"{configuration['effect_summary']}"
        )
    counterfactual = ablation["source_counterfactual"]
    lines.extend(
        [
            "",
            (
                f"Removing `{counterfactual['removed_record_id']}` changed aggregate contract "
                f"status from `{counterfactual['before']['workflow']['contract_release_status']}` "
                f"to `{counterfactual['after']['workflow']['contract_release_status']}`. The "
                "removed contradiction was age evidence. This changes what the contract permits; "
                "it does not prove identity."
            ),
            "",
            "Evidence-contract-node removal is **Not measured** because the contract is not an independently disableable benchmark node in the current implementation.",
            "",
            "## Limitations",
            "",
            "- Deterministic mock outputs are fixtures used to exercise workflow paths; they are not LLM quality measurements.",
            "- The archived Prompt V2 evidence is one live extraction run and has no live same-model single-prompt comparator.",
            "- The 21-case harness is synthetic and small; zero observed false links is not a real-world safety guarantee.",
            "- The selected benchmark ablations produced no primary-metric or case-level change. That no-effect result is retained rather than hidden.",
            "- THREADLINE proposes possible record connections for authorized review and never confirms identity.",
            "",
            "## Reproduction",
            "",
            "From `backend`:",
            "",
            "```powershell",
            ".\\.venv\\Scripts\\python.exe scripts\\build_submission_evidence.py",
            "```",
            "",
        ]
    )
    return "\n".join(lines)


async def build_submission_evidence(
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now(UTC).isoformat()
    settings = Settings(provider_mode="mock")
    provider: MockProvider[Any] = MockProvider()
    dataset = generate_benchmark(BENCHMARK_CONFIG)
    benchmark_runner = BenchmarkRunner(settings=settings, provider=provider)
    benchmark = await benchmark_runner.run(
        dataset,
        mode=ProviderMode.mock,
        candidate_k=5,
    )
    judge_comparison, source_counterfactual = await _judge_comparison(settings, provider)
    ablation_run = await AblationRunner(benchmark_runner).run(
        dataset,
        mode=ProviderMode.mock,
        selected_nodes=["prosecutor", "rivals", "adjudicate"],
    )

    systems = [
        {
            "system_id": system.system_id,
            "system_name": SUBMISSION_SYSTEM_NAMES.get(
                system.system_id, system.system_name
            ),
            "evaluation_label": DETERMINISTIC_LABEL,
            "metrics": [
                metric
                for metric in _metric_rows(system)
                if metric["metric_id"] != "average_duration_ms"
            ],
            "case_count": len(system.outputs),
            "model_calls": sum(output.model_calls for output in system.outputs),
            "failures": sum(output.failures for output in system.outputs),
            "retries": sum(output.retries for output in system.outputs),
            "latency": "Not reported for deterministic mock replay",
            "cost": "Not applicable to deterministic mock replay",
        }
        for system in benchmark.systems
    ]
    results = {
        "artifact_id": "THREADLINE-SUBMISSION-EVIDENCE-V1",
        "schema_version": "threadline-submission-evidence/1.0.0",
        "generated_at": generated_at,
        "code_state": _git_state(),
        "synthetic_only": True,
        "safety_scope": (
            "Possible record connections for authorized human review; no autonomous identity confirmation."
        ),
        "deterministic_benchmark": {
            "evaluation_label": DETERMINISTIC_LABEL,
            "benchmark_id": dataset.benchmark_id,
            "dataset_content_hash": dataset.content_hash,
            "configuration": BENCHMARK_CONFIG.model_dump(mode="json"),
            "fixture_counts": {
                "identities": len(dataset.identities),
                "records": len(dataset.records),
                "cases": len(dataset.ground_truth),
                "same_identity_cases": sum(
                    case.ground_truth_relation == "same_identity"
                    for case in dataset.ground_truth
                ),
                "different_identity_cases": sum(
                    case.ground_truth_relation == "different_identity"
                    for case in dataset.ground_truth
                ),
                "genuinely_ambiguous_cases": sum(
                    case.ground_truth_relation == "genuinely_ambiguous"
                    for case in dataset.ground_truth
                ),
            },
            "provider": {
                "mode": provider.mode,
                "model": provider.model_name,
                "temperature": 0.0,
            },
            "systems": systems,
        },
        "judge_case_comparison": judge_comparison,
        "archived_live_prompt_v2": _archived_live_v2(),
        "limitations": [
            "Deterministic mock replay results are not model-performance measurements.",
            "The archived live run evaluates extraction plus deterministic policy, not a same-model single-prompt comparator.",
            "All identities and cases are synthetic; no operational humanitarian validation has occurred.",
        ],
    }

    raw_cases: list[dict[str, Any]] = []
    outputs_by_system = {
        system.system_id: {output.case_id: output for output in system.outputs}
        for system in benchmark.systems
    }
    for case in dataset.ground_truth:
        request = request_for_case(
            dataset,
            case,
            ProviderMode.mock,
            candidate_k=5,
        )
        raw_cases.append(
            {
                "case_id": case.case_id,
                "ground_truth_relation": case.ground_truth_relation,
                "expected_classification": case.expected_classification.value,
                "input_manifest": build_input_manifest(request),
                "records": [
                    {
                        "record_id": record.record_id,
                        "source_type": record.source_type,
                        "language": record.language,
                        "text": record.text,
                    }
                    for record in request.records
                ],
                "systems": {
                    system_id: _stable_system_output(outputs[case.case_id])
                    for system_id, outputs in outputs_by_system.items()
                },
            }
        )
    raw_outputs = {
        "artifact_id": "THREADLINE-SUBMISSION-RAW-OUTPUTS-V1",
        "schema_version": "threadline-submission-raw-outputs/1.0.0",
        "generated_at": generated_at,
        "evaluation_label": DETERMINISTIC_LABEL,
        "benchmark_id": dataset.benchmark_id,
        "dataset_content_hash": dataset.content_hash,
        "cases": raw_cases,
        "judge_case": judge_comparison,
    }

    ablation_configurations: list[dict[str, Any]] = []
    operational_metric_ids = {"model_calls", "failures", "retries"}
    full_metrics = {
        metric.metric_id: metric.value
        for metric in ablation_run.configurations[0].metrics
        if metric.metric_id != "average_duration_ms"
    }
    for configuration in ablation_run.configurations:
        metrics = [
            metric
            for metric in _metric_rows(configuration)
            if metric["metric_id"] != "average_duration_ms"
        ]
        changed_metrics = {
            metric["metric_id"]: round(
                float(metric["value"]) - full_metrics[metric["metric_id"]], 3
            )
            for metric in metrics
            if metric["metric_id"] in full_metrics
            and float(metric["value"]) != full_metrics[metric["metric_id"]]
        }
        changed_quality_metrics = {
            key: value
            for key, value in changed_metrics.items()
            if key not in operational_metric_ids
        }
        changed_operational_metrics = {
            key: value
            for key, value in changed_metrics.items()
            if key in operational_metric_ids
        }
        if configuration.configuration_id == "full":
            effect_summary = "Reference configuration; no nodes disabled."
        elif not changed_quality_metrics and not configuration.affected_case_ids:
            effect_summary = (
                "No primary quality/safety metric or case-level change; affected cases: 0."
            )
        else:
            effect_summary = (
                "Measured quality or case-level changes are listed; "
                f"affected cases: {len(configuration.affected_case_ids)}."
            )
        if changed_operational_metrics:
            deltas = ", ".join(
                f"{key} {value:+g}" for key, value in changed_operational_metrics.items()
            )
            effect_summary += f" Operational harness delta: {deltas}."
        ablation_configurations.append(
            {
                "configuration_id": configuration.configuration_id,
                "disabled_nodes": configuration.disabled_nodes,
                "metrics": metrics,
                "changed_quality_metrics": changed_quality_metrics,
                "changed_operational_metrics": changed_operational_metrics,
                "affected_case_ids": configuration.affected_case_ids,
                "newly_introduced_errors": [
                    error.model_dump(mode="json")
                    for error in configuration.newly_introduced_errors
                ],
                "effect_summary": effect_summary,
            }
        )
    ablation = {
        "artifact_id": "THREADLINE-SUBMISSION-ABLATION-COUNTERFACTUAL-V1",
        "schema_version": "threadline-submission-ablation/1.0.0",
        "generated_at": generated_at,
        "evaluation_label": DETERMINISTIC_LABEL,
        "benchmark_ablations": {
            "benchmark_id": dataset.benchmark_id,
            "dataset_content_hash": dataset.content_hash,
            "configurations": ablation_configurations,
            "honest_result": (
                "The selected node removals produced no measured primary-metric or case-level "
                "change on this harness. This artifact does not claim those no-effect ablations "
                "prove component value."
            ),
        },
        "evidence_contract_node_ablation": {
            "status": "Not measured",
            "reason": (
                "The evidence contract is not an independently disableable benchmark node in "
                "the current implementation."
            ),
        },
        "source_counterfactual": source_counterfactual,
    }

    results_path = output_dir / "results.json"
    raw_path = output_dir / "raw-outputs.json"
    ablation_path = output_dir / "ablation-counterfactual.json"
    csv_path = output_dir / "results.csv"
    report_path = output_dir / "benchmark-report.md"
    results_path.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n", "utf-8")
    raw_path.write_text(
        json.dumps(raw_outputs, indent=2, ensure_ascii=False) + "\n", "utf-8"
    )
    ablation_path.write_text(
        json.dumps(ablation, indent=2, ensure_ascii=False) + "\n", "utf-8"
    )
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "evidence_track",
                "evaluation_label",
                "system_id",
                "system_name",
                "metric_id",
                "value",
                "numerator",
                "denominator",
                "formula",
            ],
        )
        writer.writeheader()
        for system in systems:
            for metric in system["metrics"]:
                writer.writerow(
                    {
                        "evidence_track": "deterministic_mock_replay",
                        "evaluation_label": DETERMINISTIC_LABEL,
                        "system_id": system["system_id"],
                        "system_name": system["system_name"],
                        **metric,
                    }
                )
    report_path.write_text(_report_markdown(results, ablation), "utf-8")
    return {
        "results": results_path,
        "csv": csv_path,
        "raw_outputs": raw_path,
        "ablation_counterfactual": ablation_path,
        "benchmark_report": report_path,
    }


async def main() -> None:
    outputs = await build_submission_evidence()
    for name, path in outputs.items():
        print(f"{name}={path} sha256={_sha256_file(path)}")


if __name__ == "__main__":
    asyncio.run(main())
