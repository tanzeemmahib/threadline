from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from typing import Any

from app.schemas.models import (
    AuditActorType,
    AuditChainEvent,
    AuditEvent,
    AuditIntegrityResult,
    AuditIntegrityStatus,
    CandidateConnection,
    EvidenceContract,
    WorkflowTraceDetail,
)
from app.services.canonical_json import canonical_sha256

AUDIT_SCHEMA_VERSION = "threadline-audit-event/1.1.0"
AUDIT_VERIFIER_VERSION = "threadline-audit-verifier/1.0.0"
HASH_ALGORITHM = "sha256"
GENESIS_HASH = hashlib.sha256(b"THREADLINE_AUDIT_GENESIS_V1").hexdigest()


def audit_hash_envelope(event: AuditChainEvent | dict[str, Any]) -> dict[str, Any]:
    value = event if isinstance(event, dict) else event.model_dump(mode="python")
    created_at = value["created_at"]
    if isinstance(created_at, datetime):
        created_at = created_at.isoformat()
    actor_type = value.get("actor_type", AuditActorType.system)
    if isinstance(actor_type, AuditActorType):
        actor_type = actor_type.value
    return {
        "event_id": value["event_id"],
        "workflow_run_id": value["workflow_run_id"],
        "contract_id": value.get("contract_id"),
        "candidate_id": value.get("candidate_id"),
        "case_id": value.get("case_id"),
        "referenced_artifact_ids": value.get("referenced_artifact_ids", []),
        "workflow_version": value.get("workflow_version", "threadline-workflow/2.0.0"),
        "sequence_number": value["sequence_number"],
        "event_type": value["event_type"],
        "actor_type": actor_type,
        "actor_id": value.get("actor_id"),
        "created_at": created_at,
        "payload_hash": value["payload_hash"],
        "previous_event_hash": value["previous_event_hash"],
        "schema_version": value["schema_version"],
        "hash_algorithm": value["hash_algorithm"],
    }


def _event_id(envelope: dict[str, Any]) -> str:
    identity = {key: value for key, value in envelope.items() if key != "event_id"}
    digest = canonical_sha256(identity)[:20]
    return f"CHAIN-{digest.upper()}"


def append_audit_event(
    events: list[AuditChainEvent],
    *,
    workflow_run_id: str,
    event_type: str,
    payload: dict[str, Any],
    created_at: datetime,
    actor_type: AuditActorType = AuditActorType.system,
    actor_id: str | None = None,
    contract_id: str | None = None,
    candidate_id: str | None = None,
    case_id: str | None = None,
    referenced_artifact_ids: list[str] | None = None,
    workflow_version: str = "threadline-workflow/2.0.0",
) -> AuditChainEvent:
    sequence_number = len(events) + 1
    previous_hash = events[-1].event_hash if events else GENESIS_HASH
    payload_hash = canonical_sha256(payload)
    normalized_actor_type = AuditActorType(actor_type)
    provisional: dict[str, Any] = {
        "event_id": "",
        "workflow_run_id": workflow_run_id,
        "contract_id": contract_id,
        "candidate_id": candidate_id,
        "case_id": case_id,
        "referenced_artifact_ids": referenced_artifact_ids or [],
        "workflow_version": workflow_version,
        "sequence_number": sequence_number,
        "event_type": event_type,
        "actor_type": normalized_actor_type.value,
        "actor_id": actor_id,
        "created_at": created_at.isoformat(),
        "payload_hash": payload_hash,
        "previous_event_hash": previous_hash,
        "schema_version": AUDIT_SCHEMA_VERSION,
        "hash_algorithm": HASH_ALGORITHM,
    }
    event_id = _event_id(provisional)
    provisional["event_id"] = event_id
    event_hash = canonical_sha256(provisional)
    event = AuditChainEvent(
        event_id=event_id,
        workflow_run_id=workflow_run_id,
        contract_id=contract_id,
        candidate_id=candidate_id,
        case_id=case_id,
        referenced_artifact_ids=referenced_artifact_ids or [],
        workflow_version=workflow_version,
        sequence_number=sequence_number,
        event_type=event_type,
        actor_type=normalized_actor_type,
        actor_id=actor_id,
        created_at=created_at,
        payload=payload,
        payload_hash=payload_hash,
        previous_event_hash=previous_hash,
        event_hash=event_hash,
    )
    events.append(event)
    return event


def build_analysis_audit_chain(
    *,
    workflow_run_id: str,
    case_id: str,
    record_ids: list[str],
    traces: list[WorkflowTraceDetail],
    legacy_events: list[AuditEvent],
    candidates: list[CandidateConnection],
    contracts: list[EvidenceContract],
    created_at: datetime,
) -> list[AuditChainEvent]:
    events: list[AuditChainEvent] = []
    base = created_at.astimezone(UTC) - timedelta(seconds=100)

    def add(event_type: str, payload: dict[str, Any], **scope: Any) -> None:
        append_audit_event(
            events,
            workflow_run_id=workflow_run_id,
            event_type=event_type,
            payload=payload,
            created_at=base + timedelta(milliseconds=len(events)),
            case_id=case_id,
            **scope,
        )

    add("workflow_run_created", {"case_id": case_id, "workflow_version": "1.0.0"})
    add("input_package_accepted", {"record_ids": record_ids, "record_count": len(record_ids)})
    for record_id in record_ids:
        add(
            "source_ingested",
            {"source_document_id": record_id},
            referenced_artifact_ids=[record_id],
        )
    for legacy in legacy_events:
        normalized_type = legacy.event_type.lower().replace(" ", "_")
        mapped = {
            "field_extracted": "evidence_span_extracted",
            "normalization_variant_added": "input_package_normalized",
            "candidate_retrieved": "candidate_generated",
            "contradiction_found": "conflict_detected",
            "rival_evaluated": "rival_comparison_created",
            "adjudication_produced": "score_computed",
            "human_review_requested": "human_review_requested",
        }.get(normalized_type, normalized_type)
        add(
            mapped,
            {
                "legacy_event_id": legacy.event_id,
                "source_record_ids": legacy.source_record_ids,
                "action": legacy.action,
                "reason": legacy.reason,
            },
            actor_type=(
                AuditActorType.human
                if legacy.machine_or_human == "human"
                else AuditActorType.system
            ),
            actor_id=legacy.actor,
        )
    for candidate in candidates:
        add(
            "score_computed",
            {
                "rank": candidate.rank,
                "retrieval_score": candidate.retrieval_score,
                "score_components": [
                    item.model_dump(mode="json") for item in candidate.score_components
                ],
            },
            candidate_id=candidate.candidate_id,
        )
    validated_span_ids: set[str] = set()
    for contract in contracts:
        claims_by_type: dict[str, list[str]] = {}
        for claim in contract.claims:
            claims_by_type.setdefault(claim.claim_type.value, []).append(claim.claim_id)
            for span in claim.source_spans:
                if span.span_id in validated_span_ids:
                    continue
                validated_span_ids.add(span.span_id)
                add(
                    "span_validated",
                    {
                        "span_id": span.span_id,
                        "validation_status": span.validation_status,
                        "content_hash": span.content_hash,
                    },
                    contract_id=contract.contract_id,
                    candidate_id=contract.candidate_id,
                    referenced_artifact_ids=[span.record_id, span.span_id],
                )
        for claim_type, claim_ids in sorted(claims_by_type.items()):
            add(
                "claim_normalized"
                if claim_type == "normalized_representation"
                else "claim_extracted"
                if claim_type == "extracted_fact"
                else "claim_derived",
                {"claim_ids": claim_ids, "claim_type": claim_type},
                contract_id=contract.contract_id,
                candidate_id=contract.candidate_id,
                referenced_artifact_ids=claim_ids,
            )
        add(
            "candidate_ledger_updated",
            {
                "ledger_id": contract.candidate_ledger.ledger_id
                if contract.candidate_ledger
                else None
            },
            contract_id=contract.contract_id,
            candidate_id=contract.candidate_id,
            referenced_artifact_ids=[contract.candidate_ledger.ledger_id]
            if contract.candidate_ledger
            else [],
        )
        add(
            "contract_evaluation_started",
            {
                "verifier_version": contract.verifier_version,
                "rule_set_version": contract.rule_set_version,
            },
            contract_id=contract.contract_id,
            candidate_id=contract.candidate_id,
            referenced_artifact_ids=[contract.contract_id],
        )
        for result in contract.rule_results:
            add(
                "rule_evaluated",
                {
                    "rule_id": result.rule_id,
                    "passed": result.passed,
                    "rule_class": result.rule_class.value,
                    "status": result.status.value,
                    "reason_code": result.reason_code,
                    "affected_claim_ids": result.affected_claim_ids,
                },
                contract_id=contract.contract_id,
                candidate_id=contract.candidate_id,
                referenced_artifact_ids=[result.rule_id, *result.input_artifact_ids],
            )
        add(
            "contract_passed" if contract.release_allowed else "contract_blocked",
            {
                "contract_status": contract.contract_status.value,
                "release_allowed": contract.release_allowed,
            },
            contract_id=contract.contract_id,
            candidate_id=contract.candidate_id,
        )
        if not contract.release_allowed:
            add(
                "classification_withheld",
                {"reason": "Evidence contract did not permit release."},
                contract_id=contract.contract_id,
                candidate_id=contract.candidate_id,
            )
    add(
        "analysis_response_released",
        {
            "decision_payload_released": all(item.release_allowed for item in contracts),
            "contract_ids": [item.contract_id for item in contracts],
            "trace_node_ids": [trace.node_id for trace in traces],
        },
    )
    return events


def verify_audit_chain(workflow_run_id: str, events: list[AuditChainEvent]) -> AuditIntegrityResult:
    try:
        if not events:
            return AuditIntegrityResult(
                workflow_run_id=workflow_run_id,
                status=AuditIntegrityStatus.incomplete,
                valid=False,
                missing_sequence_numbers=[1],
                verified_event_count=0,
            )
        sequence_numbers = [event.sequence_number for event in events]
        duplicates = sorted(
            {number for number in sequence_numbers if sequence_numbers.count(number) > 1}
        )
        maximum = max(sequence_numbers)
        missing = sorted(set(range(1, maximum + 1)) - set(sequence_numbers))
        if duplicates or missing:
            first_sequence = min([*duplicates, *missing])
            return AuditIntegrityResult(
                workflow_run_id=workflow_run_id,
                status=AuditIntegrityStatus.incomplete,
                valid=False,
                first_invalid_sequence=first_sequence,
                missing_sequence_numbers=missing,
                duplicated_sequence_numbers=duplicates,
                verified_event_count=max(0, first_sequence - 1),
            )
        previous_hash = GENESIS_HASH
        for index, event in enumerate(events, start=1):
            if (
                event.schema_version != AUDIT_SCHEMA_VERSION
                or event.hash_algorithm != HASH_ALGORITHM
            ):
                return AuditIntegrityResult(
                    workflow_run_id=workflow_run_id,
                    status=AuditIntegrityStatus.unsupported_schema,
                    valid=False,
                    first_invalid_event_id=event.event_id,
                    first_invalid_sequence=event.sequence_number,
                    verified_event_count=index - 1,
                )
            expected_payload = canonical_sha256(event.payload)
            envelope = audit_hash_envelope(event)
            expected_event_id = _event_id(envelope)
            expected_hash = canonical_sha256(envelope)
            if (
                event.workflow_run_id != workflow_run_id
                or event.sequence_number != index
                or event.event_id != expected_event_id
                or event.previous_event_hash != previous_hash
                or event.payload_hash != expected_payload
                or event.event_hash != expected_hash
            ):
                return AuditIntegrityResult(
                    workflow_run_id=workflow_run_id,
                    status=AuditIntegrityStatus.broken,
                    valid=False,
                    first_invalid_event_id=event.event_id,
                    first_invalid_sequence=event.sequence_number,
                    expected_previous_hash=previous_hash,
                    observed_previous_hash=event.previous_event_hash,
                    expected_payload_hash=expected_payload,
                    observed_payload_hash=event.payload_hash,
                    expected_event_hash=expected_hash,
                    observed_event_hash=event.event_hash,
                    verified_event_count=index - 1,
                )
            previous_hash = event.event_hash
        return AuditIntegrityResult(
            workflow_run_id=workflow_run_id,
            status=AuditIntegrityStatus.verified,
            valid=True,
            verified_event_count=len(events),
            terminal_hash=events[-1].event_hash,
        )
    except Exception:
        return AuditIntegrityResult(
            workflow_run_id=workflow_run_id,
            status=AuditIntegrityStatus.verifier_error,
            valid=False,
            verified_event_count=0,
        )
