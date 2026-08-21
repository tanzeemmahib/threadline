"""Build the canonical, artifact-backed data source for Reverie judge surfaces.

The Prompt Lab case comparison is a credential-free deterministic replay. Archived
live-provider extraction evidence is attached separately and is never described as
a one-shot model comparison. Prompt-version results remain separated by cohort.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.baselines.runner import BaselineRunner
from app.config import Settings
from app.prompts import load_prompt
from app.providers.mock_provider import MockProvider
from app.schemas.models import (
    AnalyzeOptions,
    AnalyzeRequest,
    IncidentInput,
    ProviderMode,
    RecordInput,
)
from app.services.identity_benchmark import RECORD_EXPECTED_FIELDS, load_benchmark
from app.v1_demo import v1_analyze_request

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = BACKEND_ROOT.parent
OUTPUT_PATH = REPOSITORY_ROOT / "docs" / "submission" / "reverie-prompt-lab.json"
IDENTITY_FIXTURE = BACKEND_ROOT / "fixtures" / "identity_benchmark.json"

CASE_SPECS = (
    {
        "case_id": "PROMPT-LAB-CROSS-SCRIPT",
        "kind": "cross_script_partial",
        "fixture_incident_id": "INC-CLEAR-MATCH-TRANSLITERATION",
        "title": "Cross-script evidence with partial identity detail",
        "question": "Can native-script and transliterated records support a careful connection?",
    },
    {
        "case_id": "PROMPT-LAB-SHARED-CONTACT",
        "kind": "shared_contact_insufficient",
        "fixture_incident_id": "INC-REUSED-PHONE",
        "title": "A shared household contact is not identity proof",
        "question": "Does a reused family phone justify connecting two different names?",
    },
    {
        "case_id": "PROMPT-LAB-BLOCKING-CONFLICT",
        "kind": "blocking_identity_conflict",
        "fixture_incident_id": "INC-CLEAR-NONMATCH-CONFLICTING-DOB",
        "title": "A convincing overlap stopped by a material conflict",
        "question": "Can matching name and phone override incompatible dates of birth?",
    },
)

LIVE_ARTIFACTS = {
    "targeted_v1": BACKEND_ROOT
    / "data/live_runs_phase11/targeted-prompt-v1-run-1/live-artifact.json",
    "targeted_v2": BACKEND_ROOT
    / "data/live_runs_phase11/targeted-prompt-v2-run-1/live-artifact.json",
    "full_v2": BACKEND_ROOT / "data/live_runs_phase11/full-prompt-v2-run-1/live-artifact.json",
    "full_v3": BACKEND_ROOT / "data/live_runs_phase13/full-prompt-v3-run-1/live-artifact.json",
}


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _relative(path: Path) -> str:
    return str(path.relative_to(REPOSITORY_ROOT)).replace("\\", "/")


def _prompt(template_id: str, version: str = "v1") -> dict[str, Any]:
    template = load_prompt(template_id, version)
    path = BACKEND_ROOT / "app/prompts/templates" / f"{template_id}.{version}.txt"
    return {
        "template_id": template.template_id,
        "version": template.version,
        "sha256": _sha256_file(path),
        "source_path": _relative(path),
        "text": template.content,
    }


def _incident_request(incident: dict[str, Any]) -> AnalyzeRequest:
    return AnalyzeRequest(
        incident=IncidentInput(
            incident_id=incident["incident_id"],
            name=incident["description"],
            languages=sorted({record["language"] for record in incident["records"]}),
            description=incident["description"],
            reviewer_constraints=[
                "Synthetic benchmark case",
                "Authorized human review required",
                "No autonomous identity determination",
            ],
        ),
        records=[RecordInput.model_validate(record) for record in incident["records"]],
        options=AnalyzeOptions(provider_mode=ProviderMode.mock, candidate_limit=5),
    )


def _stable_span(span: dict[str, Any]) -> dict[str, Any]:
    return {
        key: span.get(key)
        for key in (
            "span_id",
            "record_id",
            "field",
            "quote",
            "start",
            "end",
            "certainty",
            "extraction_method",
            "valid",
            "validation_error",
        )
    }


def _stable_candidate(candidate: dict[str, Any] | None) -> dict[str, Any] | None:
    if not candidate:
        return None
    decision = candidate.get("linkage_decision") or {}
    return {
        "candidate_id": candidate.get("candidate_id"),
        "record_ids": [candidate.get("record_a_id"), candidate.get("record_b_id")],
        "classification": candidate.get("classification_code"),
        "label": candidate.get("label"),
        "review_status": candidate.get("review_status"),
        "supporting_summary": candidate.get("supporting_summary"),
        "opposing_summary": candidate.get("opposing_summary"),
        "compatibility_factors": candidate.get("compatibility_factors", []),
        "conflicts": candidate.get("conflicts", []),
        "rivals": candidate.get("rivals", []),
        "candidate_generation_rules": candidate.get("candidate_generation_rules", []),
        "pairwise_comparisons": candidate.get("pairwise_comparisons", []),
        "linkage_decision": {
            "state": decision.get("state"),
            "reason_codes": decision.get("reason_codes", []),
            "total_score": decision.get("total_score"),
            "decision_threshold_version": decision.get("decision_threshold_version"),
            "strongest_supporting": decision.get("strongest_supporting", []),
            "strongest_conflicting": decision.get("strongest_conflicting", []),
            "blocking_conflicts": decision.get("blocking_conflicts", []),
            "missing_critical": decision.get("missing_critical", []),
            "llm_contributed": decision.get("llm_contributed"),
            "false_merge_risk": decision.get("false_merge_risk"),
        },
    }


def _stable_contract(contract: dict[str, Any] | None) -> dict[str, Any] | None:
    if not contract:
        return None
    return {
        "contract_id": contract.get("contract_id"),
        "candidate_id": contract.get("candidate_id"),
        "contract_status": contract.get("contract_status"),
        "release_allowed_for_authorized_review": contract.get("release_allowed"),
        "rule_results": [
            {
                key: rule.get(key)
                for key in (
                    "rule_id",
                    "status",
                    "reason_code",
                    "severity",
                    "explanation",
                    "affected_evidence_span_ids",
                )
            }
            for rule in contract.get("rule_results", [])
        ],
    }


def _live_raw_records() -> tuple[dict[str, Any], Path]:
    artifact_path = LIVE_ARTIFACTS["full_v2"]
    raw_path = artifact_path.with_name("raw-outputs.json")
    return json.loads(raw_path.read_text("utf-8"))["records"], raw_path


def _archived_live_extraction(record_id: str, rows: dict[str, Any]) -> dict[str, Any]:
    row = rows[record_id]
    extracted = {field["key"] for field in row.get("fields", [])}
    expected = RECORD_EXPECTED_FIELDS[record_id]
    return {
        "evidence_track": "archived_live_provider_extraction",
        "run_id": "full-prompt-v2-run-1",
        "prompt_version": "v2",
        "status": row["status"],
        "attempts": row["attempts"],
        "latency_ms": row["latency_ms"],
        "token_usage": row["tokens"],
        "fields": row.get("fields", []),
        "raw_provider_output": row.get("raw_output"),
        "expected_field_keys": sorted(expected),
        "supported_field_keys": sorted(extracted & expected),
        "unsupported_field_keys": sorted(extracted - expected),
        "missed_field_keys": sorted(expected - extracted),
    }


def _metrics(system: dict[str, Any], available_spans: list[dict[str, Any]]) -> dict[str, Any]:
    citations = system.get("cited_evidence", [])
    valid = [span for span in citations if span.get("valid")]
    denominator = len(available_spans)
    return {
        "schema_valid": True,
        "supported_field_count": len(valid),
        "unsupported_field_count": len(citations) - len(valid),
        "exact_citation_count": len(valid),
        "available_source_span_count": denominator,
        "source_span_coverage": round(len(valid) / denominator, 4) if denominator else None,
    }


def _system_result(system: Any, available_spans: list[dict[str, Any]]) -> dict[str, Any]:
    output = system.output
    candidate = output.get("candidate")
    workflow = output.get("workflow_response") or {}
    contracts = workflow.get("evidence_contracts", [])
    selected = {
        key: output.get(key)
        for key in (
            "classification",
            "candidate_record_ids",
            "cited_evidence_span_ids",
            "supporting_evidence",
            "contradictions",
            "uncertainty",
        )
        if key in output
    }
    return {
        "system_id": system.system_id,
        "system_name": system.system_name,
        "evaluation_label": "Deterministic mock replay - not model performance.",
        "classification": system.classification.value,
        "candidate_record_ids": system.candidate_record_ids,
        "model_calls": system.model_calls,
        "prompt": (
            _prompt("structured_baseline")
            if system.system_id == "structured"
            else _prompt("extraction", "v2")
        ),
        "model_config": {
            "provider": "mock",
            "model": "deterministic-fixture",
            "temperature": 0.0,
            "network_required": False,
        },
        "raw_provider_output": selected if system.system_id == "structured" else None,
        "validated_structured_output": selected,
        "metrics": _metrics(system.model_dump(mode="json"), available_spans),
        "cited_evidence": [
            _stable_span(span.model_dump(mode="json")) for span in system.cited_evidence
        ],
        "candidate": _stable_candidate(candidate),
        "evidence_contract": _stable_contract(contracts[0] if contracts else None),
        "workflow_trace": [
            {
                key: item.get(key)
                for key in ("node_id", "order", "name", "category", "purpose", "method")
            }
            for item in workflow.get("workflow_trace", [])
        ],
    }


async def _build_case(
    spec: dict[str, str],
    incident: dict[str, Any],
    settings: Settings,
    provider: MockProvider[Any],
    live_rows: dict[str, Any],
) -> dict[str, Any]:
    request = _incident_request(incident)
    response = await BaselineRunner(settings=settings, provider=provider).run(request)
    systems = {system.system_id: system for system in response.systems}
    threadline = systems["threadline"]
    workflow = threadline.output["workflow_response"]
    source_spans = [
        _stable_span(span)
        for record in workflow["records"]
        for span in record["evidence_spans"]
        if span["valid"]
    ]
    one_shot_result = _system_result(systems["structured"], source_spans)
    workflow_result = _system_result(threadline, source_spans)
    manifests = [
        systems["structured"].output["input_manifest"],
        threadline.output["input_manifest"],
    ]
    assert manifests[0] == manifests[1]
    decision = workflow_result["candidate"]["linkage_decision"]
    return {
        **spec,
        "synthetic_only": True,
        "ground_truth": incident["ground_truth"],
        "input_manifest": manifests[0],
        "identical_input_verified": True,
        "records": [
            {
                **record.model_dump(mode="json"),
                "text_sha256": _sha256_bytes(record.text.encode("utf-8")),
                "archived_live_v2_extraction": _archived_live_extraction(
                    record.record_id, live_rows
                ),
            }
            for record in request.records
        ],
        "source_spans": source_spans,
        "systems": {
            "one_shot": one_shot_result,
            "threadline": workflow_result,
        },
        "comparison_dimensions": {
            "schema_validity": {
                "one_shot": one_shot_result["metrics"]["schema_valid"],
                "threadline": workflow_result["metrics"]["schema_valid"],
            },
            "source_span_coverage": {
                "one_shot": one_shot_result["metrics"]["source_span_coverage"],
                "threadline": workflow_result["metrics"]["source_span_coverage"],
            },
            "supported_fields": {
                "one_shot": one_shot_result["metrics"]["supported_field_count"],
                "threadline": workflow_result["metrics"]["supported_field_count"],
            },
            "unsupported_fields": {
                "one_shot": one_shot_result["metrics"]["unsupported_field_count"],
                "threadline": workflow_result["metrics"]["unsupported_field_count"],
            },
            "identity_outcome": {
                "one_shot": one_shot_result["classification"],
                "threadline": decision["state"],
            },
            "deterministic_conflict_handling": {
                "one_shot": False,
                "threadline": True,
            },
            "auditability": {
                "one_shot": "One parsed response with exact citations; no independent policy gate.",
                "threadline": (
                    f"{len(workflow_result['workflow_trace'])} staged trace entries plus "
                    "a deterministic evidence contract."
                ),
            },
        },
        "decision": {
            "state": decision["state"],
            "reason_codes": decision["reason_codes"],
            "blocking_conflicts": decision["blocking_conflicts"],
            "release_allowed_for_authorized_review": (
                workflow_result["evidence_contract"] or {}
            ).get("release_allowed_for_authorized_review"),
            "safety_notice": (
                "Possible connection only. THREADLINE never autonomously confirms identity."
            ),
        },
    }


def _live_run(key: str) -> dict[str, Any]:
    path = LIVE_ARTIFACTS[key]
    artifact = json.loads(path.read_text("utf-8"))
    raw_path = path.with_name("raw-outputs.json")
    rows = json.loads(raw_path.read_text("utf-8"))["records"]
    successful = [row for row in rows.values() if row["status"] == "ok"]
    latencies = sorted(float(row["latency_ms"]) for row in successful)
    return {
        "run_id": artifact["run_id"],
        "execution_mode": artifact["execution_mode"],
        "provider": artifact["provider"],
        "model": artifact["model"],
        "temperature": artifact["temperature"],
        "prompt_version": artifact["prompt_version"],
        "prompt_sha256": _prompt("extraction", artifact["prompt_version"])["sha256"],
        "fixture_sha256": artifact["fixture_sha256"],
        "run_timestamp_utc": datetime.fromtimestamp(artifact["timestamp"], tz=UTC).isoformat(),
        "record_count": len(rows),
        "extraction_quality": artifact["extraction_quality"],
        "decision_metrics": artifact["metrics"],
        "retrieval": artifact.get("retrieval"),
        "safety": artifact["safety"],
        "operational": {
            "successful_records": len(successful),
            "failed_records": len(rows) - len(successful),
            "median_latency_ms": (
                latencies[len(latencies) // 2]
                if len(latencies) % 2
                else sum(latencies[len(latencies) // 2 - 1 : len(latencies) // 2 + 1]) / 2
            ),
            "p95_latency_ms": latencies[math.ceil(0.95 * len(latencies)) - 1],
            "total_tokens": sum(int(row["tokens"]) for row in successful if row["tokens"]),
            "approximate_api_cost": "Not measured",
        },
        "source_files": {
            _relative(path): _sha256_file(path),
            _relative(raw_path): _sha256_file(raw_path),
        },
    }


async def _winning_story(settings: Settings, provider: MockProvider[Any]) -> dict[str, Any]:
    response = await BaselineRunner(settings=settings, provider=provider).run(
        v1_analyze_request("rival")
    )
    threadline = next(system for system in response.systems if system.system_id == "threadline")
    workflow = threadline.output["workflow_response"]
    candidates = [_stable_candidate(candidate) for candidate in workflow["candidates"]]
    contracts = [_stable_contract(contract) for contract in workflow["evidence_contracts"]]
    spans = [
        _stable_span(span)
        for record in workflow["records"]
        for span in record["evidence_spans"]
        if span["valid"]
    ]
    integrity = workflow.get("audit_integrity") or {}
    manifest = workflow.get("replay_manifest") or {}
    return {
        "case_id": "THREADLINE-WINNING-STORY-V1",
        "scenario": "rival",
        "synthetic_only": True,
        "input_manifest": threadline.output["input_manifest"],
        "records": [
            {
                "record_id": record["record_id"],
                "source_type": record["source_type"],
                "language": record["language"],
                "text": record["text"],
            }
            for record in workflow["records"]
        ],
        "source_spans": spans,
        "candidates": candidates,
        "evidence_contracts": contracts,
        "provenance": {
            "workflow_run_id": workflow.get("workflow_run_id", "Not recorded"),
            "case_id": workflow.get("case_id", "Not recorded"),
            "evidence_contracts": [
                {
                    "contract_id": contract.get("contract_id") or "Not recorded",
                    "candidate_id": contract.get("candidate_id") or "Not recorded",
                    "contract_status": contract.get("contract_status") or "Not recorded",
                    "release_allowed_for_authorized_review": contract.get(
                        "release_allowed_for_authorized_review"
                    ),
                }
                for contract in contracts
                if contract
            ],
            "audit_integrity": {
                "status": integrity.get("status", "Not recorded"),
                "valid": integrity.get("valid", "Not recorded"),
                "verified_event_count": integrity.get("verified_event_count", "Not recorded"),
                "terminal_hash": integrity.get("terminal_hash", "Not recorded"),
                "hash_algorithm": integrity.get("hash_algorithm", "Not recorded"),
                "verifier_version": integrity.get("verifier_version", "Not recorded"),
                "limitation": integrity.get("limitation", "Not recorded"),
            },
            "replay_manifest": {
                "manifest_version": manifest.get("manifest_version", "Not recorded"),
                "original_input_package_hash": manifest.get(
                    "original_input_package_hash", "Not recorded"
                ),
                "configuration_hash": manifest.get("configuration_hash", "Not recorded"),
                "prompt_template_versions": manifest.get(
                    "prompt_template_versions", "Not recorded"
                ),
                "model_identifiers": manifest.get("model_identifiers", "Not recorded"),
                "final_candidate_set_hash": manifest.get(
                    "final_candidate_set_hash", "Not recorded"
                ),
                "final_contract_hash": manifest.get("final_contract_hash", "Not recorded"),
                "final_response_hash": manifest.get("final_response_hash", "Not recorded"),
                "audit_chain_terminal_hash": manifest.get(
                    "audit_chain_terminal_hash", "Not recorded"
                ),
            },
            "replay_certificate": workflow.get("latest_replay_certificate") or "Not recorded",
            "export_artifact": "Not recorded",
        },
        "supported_pair": ["FAMILY-018", "SHELTER-204"],
        "blocked_rival_pair": ["FAMILY-018", "HOSPITAL-052"],
        "language_limitation": (
            "This locked V1 narrative fixture is English-only. The separate Prompt Lab "
            "cross-script case carries native Arabic evidence."
        ),
        "climax": (
            "One connection recovered. One false merge prevented. Every decision traceable."
        ),
    }


async def build_reverie_prompt_lab(output_path: Path = OUTPUT_PATH) -> dict[str, Any]:
    settings = Settings(provider_mode="mock")
    provider: MockProvider[Any] = MockProvider()
    incidents = {item["incident_id"]: item for item in load_benchmark()}
    live_rows, raw_path = _live_raw_records()
    cases = [
        await _build_case(
            spec,
            incidents[spec["fixture_incident_id"]],
            settings,
            provider,
            live_rows,
        )
        for spec in CASE_SPECS
    ]
    live_runs = {key: _live_run(key) for key in LIVE_ARTIFACTS}
    latest_timestamp = max(run["run_timestamp_utc"] for run in live_runs.values())
    artifact = {
        "artifact_id": "THREADLINE-REVERIE-PROMPT-LAB-V1",
        "schema_version": "threadline-reverie-prompt-lab/1.0.0",
        "generated_at": latest_timestamp,
        "timestamp_basis": "Latest timestamp among the four locked live-provider sources.",
        "synthetic_only": True,
        "safety_scope": (
            "Experimental safety and review layer for possible record connections; "
            "no autonomous identity confirmation."
        ),
        "source_artifacts": {
            _relative(IDENTITY_FIXTURE): _sha256_file(IDENTITY_FIXTURE),
            _relative(raw_path): _sha256_file(raw_path),
            **{_relative(path): _sha256_file(path) for path in LIVE_ARTIFACTS.values()},
        },
        "winning_story": await _winning_story(settings, provider),
        "cases": cases,
        "prompt_iterations": {
            "headline": (
                "Prompt V3 completed every extraction but was not promoted because precision "
                "and F1 regressed on the shared full cohort."
            ),
            "cohorts": [
                {
                    "cohort_id": "targeted-19-record-live-cohort",
                    "comparable_versions": ["v1", "v2"],
                    "runs": [live_runs["targeted_v1"], live_runs["targeted_v2"]],
                    "interpretation": (
                        "V2 improved supported-field recovery and reduced false-positive fields "
                        "on the same 19 records."
                    ),
                },
                {
                    "cohort_id": "full-58-record-live-cohort",
                    "comparable_versions": ["v2", "v3"],
                    "runs": [live_runs["full_v2"], live_runs["full_v3"]],
                    "interpretation": (
                        "V3 increased recall but produced 78 false-positive fields versus 30 "
                        "for V2; precision and F1 regressed."
                    ),
                },
            ],
            "prompt_summaries": {
                "v1": "Concise exact-span extraction with canonical-key and no-invention rules.",
                "v2": (
                    "Adds completeness, multilingual preservation, partial-value handling, and "
                    "a field-by-field extraction checklist."
                ),
                "v3": (
                    "Adds stricter subject-attachment and field-specific precision rules; not "
                    "promoted because the measured false-positive-field rate increased."
                ),
            },
            "prompts": {version: _prompt("extraction", version) for version in ("v1", "v2", "v3")},
            "promotion_decision": {
                "production_version": "v2",
                "not_promoted": "v3",
                "reason_code": "PRECISION_REGRESSION",
                "same_full_cohort": True,
                "v2_precision": live_runs["full_v2"]["extraction_quality"]["micro_precision"],
                "v3_precision": live_runs["full_v3"]["extraction_quality"]["micro_precision"],
                "v2_recall": live_runs["full_v2"]["extraction_quality"]["micro_recall"],
                "v3_recall": live_runs["full_v3"]["extraction_quality"]["micro_recall"],
                "v2_f1": live_runs["full_v2"]["extraction_quality"]["micro_f1"],
                "v3_f1": live_runs["full_v3"]["extraction_quality"]["micro_f1"],
                "v2_false_positive_fields": live_runs["full_v2"]["extraction_quality"]["total_fp"],
                "v3_false_positive_fields": live_runs["full_v3"]["extraction_quality"]["total_fp"],
            },
            "comparison_limit": (
                "No full 58-record V1 live artifact exists. V1 must not be presented as part "
                "of a three-way same-cohort ranking."
            ),
        },
        "limitations": [
            "Prompt Lab one-shot versus workflow cases are deterministic mock replays, not model performance.",
            "Archived live evidence measures extraction; it does not contain a same-model one-shot identity baseline.",
            "The cross-script case routes a possible connection to human review; it is not an autonomous link.",
            "All records are synthetic and have not been validated for operational humanitarian use.",
        ],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(artifact, indent=2, ensure_ascii=False) + "\n", "utf-8")
    return artifact


async def main() -> None:
    artifact = await build_reverie_prompt_lab()
    print(f"output={OUTPUT_PATH}")
    print(f"sha256={_sha256_file(OUTPUT_PATH)}")
    print(f"cases={len(artifact['cases'])}")


if __name__ == "__main__":
    asyncio.run(main())
