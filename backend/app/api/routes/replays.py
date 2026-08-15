from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request

from app.providers import build_provider
from app.schemas.models import (
    AnalyzeRequest,
    AnalyzeResponse,
    ProviderMode,
    ReplayCertificate,
    ReplayManifest,
    ReplayMode,
    ReplayStatus,
)
from app.services.evidence_contracts import build_release_view
from app.services.replay import (
    CONTRACT_SCHEMA_VERSION,
    RULE_SET_VERSION,
    SCORING_VERSION,
    WORKFLOW_SCHEMA_VERSION,
    build_replay_certificate,
    build_replay_manifest,
)
from app.workflow import WorkflowOrchestrator

router = APIRouter(prefix="/api/v1", tags=["replay"])


@router.post("/runs/{workflow_run_id}/replay", response_model=ReplayCertificate)
async def replay_run(workflow_run_id: str, request: Request) -> ReplayCertificate:
    repository = request.app.state.repository
    input_value = repository.get("analysis_inputs", workflow_run_id)
    response_value = repository.get("workflow_runs", workflow_run_id)
    manifest_value = repository.get("replay_manifests", workflow_run_id)
    if input_value is None or response_value is None:
        raise HTTPException(status_code=404, detail="Workflow run or replay input not found")
    if manifest_value is None:
        raise HTTPException(status_code=409, detail="Replay manifest is unavailable")
    source_request = AnalyzeRequest.model_validate(input_value)
    source_response = AnalyzeResponse.model_validate(response_value)
    expected = ReplayManifest.model_validate(manifest_value)
    started_at = datetime.now(UTC)
    repository.append_chain_event(
        workflow_run_id=workflow_run_id,
        event_type="replay_requested",
        payload={"manifest_version": expected.manifest_version},
        created_at=started_at,
    )
    repository.refresh_workflow_audit(workflow_run_id)
    versions_supported = (
        expected.workflow_schema_version == WORKFLOW_SCHEMA_VERSION
        and expected.contract_schema_version == CONTRACT_SCHEMA_VERSION
        and expected.scoring_version == SCORING_VERSION
        and expected.rule_set_version == RULE_SET_VERSION
    )
    if source_request.options.provider_mode != ProviderMode.mock or not versions_supported:
        certificate = ReplayCertificate(
            replay_id=f"REPLAY-{uuid4()}",
            source_workflow_run_id=workflow_run_id,
            replay_status=ReplayStatus.unsupported,
            replay_mode=ReplayMode.frozen_model_outputs,
            started_at=started_at,
            completed_at=datetime.now(UTC),
            manifest_version=expected.manifest_version,
            checkpoints=[],
            classification_consistent=False,
            ranking_consistent=False,
            contract_consistent=False,
            audit_chain_consistent=False,
            release_permitted=False,
            limitations=[
                "Replay is fail-closed when provider outputs are not frozen or a manifest version is unsupported."
            ],
        )
    else:
        provider = build_provider(source_request.options.provider_mode, request.app.state.settings)
        replayed = build_release_view(
            await WorkflowOrchestrator(
                settings=request.app.state.settings, provider=provider
            ).run(source_request)
        )
        replayed.replay_manifest = build_replay_manifest(source_request, replayed)
        observed = build_replay_manifest(source_request, replayed)
        certificate = build_replay_certificate(
            expected=expected,
            observed=observed,
            source=source_response,
            replayed=replayed,
            started_at=started_at,
            completed_at=datetime.now(UTC),
        )
    repository.put("replay_certificates", certificate.replay_id, certificate)
    source_response.latest_replay_certificate = certificate
    repository.put("workflow_runs", workflow_run_id, source_response)
    repository.append_chain_event(
        workflow_run_id=workflow_run_id,
        event_type=(
            "replay_completed"
            if certificate.replay_status
            in {ReplayStatus.exact_match, ReplayStatus.equivalent_match}
            else "replay_mismatch_detected"
        ),
        payload={
            "replay_id": certificate.replay_id,
            "status": certificate.replay_status.value,
            "first_divergence": certificate.first_divergence,
        },
        created_at=certificate.completed_at,
    )
    repository.refresh_workflow_audit(workflow_run_id)
    return certificate


@router.get("/replays/{replay_id}", response_model=ReplayCertificate)
async def get_replay(replay_id: str, request: Request) -> ReplayCertificate:
    value = request.app.state.repository.get("replay_certificates", replay_id)
    if value is None:
        raise HTTPException(status_code=404, detail="Replay certificate not found")
    return ReplayCertificate.model_validate(value)
