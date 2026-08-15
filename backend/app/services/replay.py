from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any

from app.schemas.models import (
    AnalyzeRequest,
    AnalyzeResponse,
    ReplayCertificate,
    ReplayCheckpoint,
    ReplayManifest,
    ReplayMode,
    ReplayStatus,
)
from app.services.canonical_json import canonical_sha256

WORKFLOW_SCHEMA_VERSION = "threadline-workflow/1.0.0"
CONTRACT_SCHEMA_VERSION = "threadline-evidence-contract/2.0.0"
SCORING_VERSION = "threadline-candidate-scoring/1.0.0"
RULE_SET_VERSION = "threadline-contract-rules/3.1.0"


def _replay_stable_value(value: Any) -> Any:
    """Remove generated identifiers/timestamps that do not affect a decision."""
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="python")
    if isinstance(value, dict):
        return {
            key: _replay_stable_value(item)
            for key, item in value.items()
            if key not in {"decision_id", "created_at"}
        }
    if isinstance(value, list):
        return [_replay_stable_value(item) for item in value]
    return value


def _response_hash(response: AnalyzeResponse) -> str:
    payload = response.model_dump(mode="python", exclude={"replay_manifest"})
    return canonical_sha256(_replay_stable_value(payload))


def build_replay_manifest(request: AnalyzeRequest, response: AnalyzeResponse) -> ReplayManifest:
    checkpoints: list[ReplayCheckpoint] = []
    prompt_versions: dict[str, str] = {}
    models: set[str] = set()
    for trace in response.workflow_trace_details:
        checkpoints.extend(
            [
                ReplayCheckpoint(
                    checkpoint_id=f"node:{trace.node_id}:input",
                    expected_hash=canonical_sha256(
                        _replay_stable_value(trace.structured_input)
                    ),
                ),
                ReplayCheckpoint(
                    checkpoint_id=f"node:{trace.node_id}:output",
                    expected_hash=canonical_sha256(
                        _replay_stable_value(trace.structured_output)
                    ),
                ),
            ]
        )
        if trace.prompt_template_id and trace.prompt_template_version:
            prompt_versions[trace.prompt_template_id] = trace.prompt_template_version
        if trace.model:
            models.update(item.strip() for item in trace.model.split(",") if item.strip())
    created_at = (
        response.workflow_trace_details[-1].completed_at
        if response.workflow_trace_details
        else datetime.now(UTC)
    )
    terminal_hash = response.audit_integrity.terminal_hash if response.audit_integrity else None
    contract_rule_versions = {
        contract.rule_set_version for contract in response.evidence_contracts
    }
    manifest_rule_version = (
        next(iter(contract_rule_versions))
        if len(contract_rule_versions) == 1
        else RULE_SET_VERSION
        if not contract_rule_versions
        else "mixed:" + ",".join(sorted(contract_rule_versions))
    )
    return ReplayManifest(
        workflow_run_id=response.workflow_run_id,
        original_input_package_hash=canonical_sha256(request),
        canonical_normalized_input_hash=canonical_sha256(response.records),
        workflow_schema_version=WORKFLOW_SCHEMA_VERSION,
        contract_schema_version=CONTRACT_SCHEMA_VERSION,
        scoring_version=SCORING_VERSION,
        rule_set_version=manifest_rule_version,
        configuration_hash=canonical_sha256(request.options),
        prompt_template_versions=prompt_versions,
        model_identifiers=sorted(models),
        deterministic_seeds=[],
        ordered_workflow_nodes=[item.node_id for item in response.workflow_trace_details],
        node_checkpoints=checkpoints,
        final_candidate_set_hash=canonical_sha256(
            _replay_stable_value(response.candidates)
        ),
        final_ranking_hash=canonical_sha256(
            [
                {
                    "candidate_id": item.candidate_id,
                    "record_ids": [item.record_a_id, item.record_b_id],
                    "rank": item.rank,
                    "score": item.retrieval_score,
                }
                for item in response.candidates
            ]
        ),
        final_contract_hash=canonical_sha256(
            _replay_stable_value(response.evidence_contracts)
        ),
        final_response_hash=_response_hash(response),
        audit_chain_terminal_hash=terminal_hash or "",
        created_at=created_at,
    )


def compare_replay_manifests(
    expected: ReplayManifest, observed: ReplayManifest
) -> list[ReplayCheckpoint]:
    expected_nodes = {item.checkpoint_id: item.expected_hash for item in expected.node_checkpoints}
    observed_nodes = {item.checkpoint_id: item.expected_hash for item in observed.node_checkpoints}
    checks = [
        (
            "manifest:input_package",
            expected.original_input_package_hash,
            observed.original_input_package_hash,
        ),
        (
            "manifest:normalized_input",
            expected.canonical_normalized_input_hash,
            observed.canonical_normalized_input_hash,
        ),
        ("manifest:configuration", expected.configuration_hash, observed.configuration_hash),
        (
            "manifest:candidate_set",
            expected.final_candidate_set_hash,
            observed.final_candidate_set_hash,
        ),
        ("manifest:ranking", expected.final_ranking_hash, observed.final_ranking_hash),
        ("manifest:contract", expected.final_contract_hash, observed.final_contract_hash),
        ("manifest:response", expected.final_response_hash, observed.final_response_hash),
        (
            "manifest:audit_terminal",
            expected.audit_chain_terminal_hash,
            observed.audit_chain_terminal_hash,
        ),
    ]
    checkpoints = [
        ReplayCheckpoint(
            checkpoint_id=checkpoint_id,
            expected_hash=expected_hash,
            observed_hash=observed_hash,
            consistent=expected_hash == observed_hash,
        )
        for checkpoint_id, expected_hash, observed_hash in checks
    ]
    for checkpoint_id, expected_hash in expected_nodes.items():
        observed_hash = observed_nodes.get(checkpoint_id)
        checkpoints.append(
            ReplayCheckpoint(
                checkpoint_id=checkpoint_id,
                expected_hash=expected_hash,
                observed_hash=observed_hash,
                consistent=expected_hash == observed_hash,
            )
        )
    return checkpoints


def build_replay_certificate(
    *,
    expected: ReplayManifest,
    observed: ReplayManifest,
    source: AnalyzeResponse,
    replayed: AnalyzeResponse,
    started_at: datetime,
    completed_at: datetime,
) -> ReplayCertificate:
    checkpoints = compare_replay_manifests(expected, observed)
    first = next((item for item in checkpoints if not item.consistent), None)
    exact = first is None
    source_classifications = [item.classification_code for item in source.candidates]
    replayed_classifications = [item.classification_code for item in replayed.candidates]
    replay_id = hashlib.sha256(
        f"{source.workflow_run_id}|{started_at.isoformat()}".encode()
    ).hexdigest()[:20]
    return ReplayCertificate(
        replay_id=f"REPLAY-{replay_id.upper()}",
        source_workflow_run_id=source.workflow_run_id,
        replay_workflow_run_id=replayed.workflow_run_id,
        replay_status=ReplayStatus.exact_match if exact else ReplayStatus.diverged,
        replay_mode=ReplayMode.deterministic,
        started_at=started_at,
        completed_at=completed_at,
        manifest_version=expected.manifest_version,
        checkpoints=checkpoints,
        first_divergence=first.checkpoint_id if first else None,
        expected_hash=first.expected_hash if first else None,
        observed_hash=first.observed_hash if first else None,
        classification_consistent=source_classifications == replayed_classifications,
        ranking_consistent=(expected.final_ranking_hash == observed.final_ranking_hash),
        contract_consistent=(expected.final_contract_hash == observed.final_contract_hash),
        audit_chain_consistent=(
            expected.audit_chain_terminal_hash == observed.audit_chain_terminal_hash
        ),
        release_permitted=(exact and replayed.contract_release_status.value == "released"),
        limitations=[
            "Exact replay is supported for the deterministic mock provider.",
            "Connected-provider replay requires frozen structured model outputs and is reported unsupported until those outputs can be replayed without a new model call.",
        ],
    )
