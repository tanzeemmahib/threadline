from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request

from app.providers import build_provider
from app.schemas.models import (
    AnalyzeRequest,
    AnalyzeResponse,
    CounterfactualCertificate,
    CounterfactualRequest,
    ProviderMode,
)
from app.services.counterfactuals import (
    derive_counterfactual_request,
    find_comparable_candidate,
    first_responsible_node,
)
from app.services.evidence_contracts import build_release_view
from app.services.replay import build_replay_manifest
from app.workflow import WorkflowOrchestrator

router = APIRouter(prefix="/api/v1", tags=["counterfactuals"])


@router.post(
    "/runs/{workflow_run_id}/counterfactuals",
    response_model=CounterfactualCertificate,
)
async def create_counterfactual(
    workflow_run_id: str, payload: CounterfactualRequest, request: Request
) -> CounterfactualCertificate:
    repository = request.app.state.repository
    input_value = repository.get("analysis_inputs", workflow_run_id)
    response_value = repository.get("workflow_runs", workflow_run_id)
    if input_value is None or response_value is None:
        raise HTTPException(status_code=404, detail="Workflow run not found")
    source_request = AnalyzeRequest.model_validate(input_value)
    source_response = AnalyzeResponse.model_validate(response_value)
    if source_request.options.provider_mode != ProviderMode.mock:
        raise HTTPException(
            status_code=409,
            detail=(
                "Counterfactual replay requires the deterministic mock provider or frozen "
                "structured model outputs."
            ),
        )
    source_candidate = next(
        (item for item in source_response.candidates if item.candidate_id == payload.candidate_id),
        None,
    )
    if source_candidate is None:
        raise HTTPException(status_code=422, detail="Candidate does not belong to workflow run")
    if payload.source_record_id and payload.source_record_id not in {
        source_candidate.record_a_id,
        source_candidate.record_b_id,
    }:
        raise HTTPException(
            status_code=422,
            detail="Source record does not belong to the selected candidate",
        )
    started_at = datetime.now(UTC)
    repository.append_chain_event(
        workflow_run_id=workflow_run_id,
        event_type="counterfactual_requested",
        payload={
            "candidate_id": payload.candidate_id,
            "counterfactual_type": payload.counterfactual_type.value,
        },
        created_at=started_at,
        candidate_id=payload.candidate_id,
    )
    repository.refresh_workflow_audit(workflow_run_id)
    try:
        derived_request, altered_ids = derive_counterfactual_request(
            source_request, source_response, payload
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    provider = build_provider(derived_request.options.provider_mode, request.app.state.settings)
    derived_response = build_release_view(
        await WorkflowOrchestrator(
            settings=request.app.state.settings, provider=provider
        ).run(derived_request)
    )
    derived_response.replay_manifest = build_replay_manifest(derived_request, derived_response)
    created_at = (
        derived_response.workflow_trace_details[-1].completed_at.isoformat()
        if derived_response.workflow_trace_details
        else datetime.now(UTC).isoformat()
    )
    repository.persist_analysis_bundle(
        request=derived_request,
        response=derived_response,
        result={
            "result_id": derived_response.workflow_run_id,
            "result_type": "counterfactual_analysis",
            "created_at": created_at,
            "provider_mode": derived_response.mode.value,
            "payload": derived_response.model_dump(mode="json"),
        },
    )
    original, observed = find_comparable_candidate(
        source_response, derived_response, payload.candidate_id
    )
    original_contract = next(
        (
            item
            for item in source_response.evidence_contracts
            if item.candidate_id == payload.candidate_id
        ),
        None,
    )
    observed_contract = next(
        (
            item
            for item in derived_response.evidence_contracts
            if observed is not None and item.candidate_id == observed.candidate_id
        ),
        None,
    )
    original_rules = (
        {item.rule_id for item in original_contract.violations} if original_contract else set()
    )
    observed_rules = (
        {item.rule_id for item in observed_contract.violations} if observed_contract else set()
    )
    original_classification = original_contract.classification if original_contract else None
    observed_classification = observed_contract.classification if observed_contract else None
    original_rank = original.rank if original else None
    observed_rank = observed.rank if observed else None
    original_score = original.retrieval_score if original else None
    observed_score = observed.retrieval_score if observed else None
    release_status = derived_response.contract_release_status
    top_changed = bool(
        source_response.candidates
        and derived_response.candidates
        and {
            source_response.candidates[0].record_a_id,
            source_response.candidates[0].record_b_id,
        }
        != {
            derived_response.candidates[0].record_a_id,
            derived_response.candidates[0].record_b_id,
        }
    )
    classification_changed = original_classification != observed_classification
    rank_changed = original_rank != observed_rank or top_changed
    decision_changed = (
        classification_changed
        or rank_changed
        or source_response.contract_release_status != release_status
        or bool(original_rules ^ observed_rules)
    )
    certificate_digest = hashlib.sha256(
        f"{workflow_run_id}|{derived_response.workflow_run_id}|{payload.model_dump_json()}".encode()
    ).hexdigest()[:20]
    certificate = CounterfactualCertificate(
        certificate_id=f"COUNTERFACTUAL-{certificate_digest.upper()}",
        original_workflow_run_id=workflow_run_id,
        counterfactual_run_id=derived_response.workflow_run_id,
        candidate_id=payload.candidate_id,
        counterfactual_type=payload.counterfactual_type,
        removed_or_altered_evidence_ids=altered_ids,
        original_classification=original_classification,
        counterfactual_classification=observed_classification,
        original_rank=original_rank,
        counterfactual_rank=observed_rank,
        original_score=original_score,
        counterfactual_score=observed_score,
        triggered_violations=sorted(observed_rules - original_rules),
        resolved_violations=sorted(original_rules - observed_rules),
        decision_changed=decision_changed,
        rank_changed=rank_changed,
        classification_changed=classification_changed,
        release_status=release_status,
        explanation=(
            "The deterministic replay changed a release-relevant outcome after the selected evidence was altered."
            if decision_changed
            else "The deterministic replay did not change classification, rank, release status, or critical contract rules."
        ),
        first_responsible_node=first_responsible_node(source_response, derived_response),
        created_at=datetime.now(UTC),
        limitations=[
            "This certificate applies only to the selected mutation and tested configuration.",
            "It does not establish that untested evidence combinations are non-critical.",
        ],
    )
    repository.put("counterfactual_certificates", certificate.certificate_id, certificate)
    source_response.counterfactual_certificates.append(certificate)
    if decision_changed and original_contract is not None:
        summary = certificate.model_dump(mode="json")
        original_contract.decision_critical_evidence.append(summary)
        repository.put("evidence_contracts", original_contract.contract_id, original_contract)
        for index, contract in enumerate(source_response.evidence_contracts):
            if contract.contract_id == original_contract.contract_id:
                source_response.evidence_contracts[index] = original_contract
        if (
            source_response.evidence_contract
            and source_response.evidence_contract.contract_id == original_contract.contract_id
        ):
            source_response.evidence_contract = original_contract
    repository.put("workflow_runs", workflow_run_id, source_response)
    repository.append_chain_event(
        workflow_run_id=workflow_run_id,
        event_type="counterfactual_completed",
        payload={
            "certificate_id": certificate.certificate_id,
            "decision_changed": decision_changed,
            "counterfactual_run_id": certificate.counterfactual_run_id,
        },
        created_at=certificate.created_at,
        candidate_id=payload.candidate_id,
    )
    repository.refresh_workflow_audit(workflow_run_id)
    return certificate


@router.get("/counterfactuals/{certificate_id}", response_model=CounterfactualCertificate)
async def get_counterfactual(certificate_id: str, request: Request) -> CounterfactualCertificate:
    value = request.app.state.repository.get("counterfactual_certificates", certificate_id)
    if value is None:
        raise HTTPException(status_code=404, detail="Counterfactual certificate not found")
    return CounterfactualCertificate.model_validate(value)
