from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.schemas.models import (
    SAFETY_NOTICE,
    AnalyzeResponse,
    AuditIntegrityResult,
    AuditIntegrityStatus,
    CandidateClaimLedger,
    CandidateConnection,
    Certainty,
    ClaimTransformation,
    ClaimType,
    Classification,
    ContractReleaseStatus,
    ContractRuleClass,
    ContractRuleResult,
    ContractSeverity,
    ContractStatus,
    ContractViolation,
    EvidenceClaim,
    EvidenceContract,
    EvidenceSpan,
    NormalizedRecord,
    RecordInput,
    RuleEvaluationStatus,
)
from app.services.canonical_json import canonical_sha256

VERIFIER_VERSION = "threadline-evidence-contracts/2.0.0"
RULE_SET_VERSION = "threadline-contract-rules/3.1.0"
CANONICAL_RULE_VERSION = "1.0.0"
REQUIRED_WORKFLOW_NODES = (
    "incident",
    "quarantine",
    "extract",
    "normalize",
    "timeline",
    "retrieve",
    "hypothesis",
    "prosecutor",
    "rivals",
    "adjudicate",
    "privacy",
    "review",
)
FORBIDDEN_RELEASE_PHRASES = (
    "confirmed_match",
    "identity_confirmed",
    "person_found",
    "guaranteed_match",
    "definitely_same_person",
    "successfully_reunited",
    "99_percent_match",
)
WITHHELD_LANGUAGE_MARKER = "[PROHIBITED RELEASE LANGUAGE WITHHELD]"


@dataclass(frozen=True, slots=True)
class ContractVerificationContext:
    records: dict[str, RecordInput]
    hard_conflict_ids: set[str]
    routing_hard_conflict_ids: set[str]
    close_rival_record_ids: set[str]
    candidate_output: dict[str, Any]
    candidate: CandidateConnection | None = None
    workflow_node_ids: tuple[str, ...] | None = None
    audit_integrity: AuditIntegrityResult | None = None
    replay_status: str | None = None
    block_hard_conflicts: bool = False


def _violation(
    rule_id: str,
    message: str,
    resolution: str,
    *,
    claim_id: str | None = None,
    rule_class: ContractRuleClass = ContractRuleClass.blocking,
    severity: ContractSeverity = ContractSeverity.critical,
    evidence_span_ids: list[str] | None = None,
) -> ContractViolation:
    digest = hashlib.sha256(f"{rule_id}|{claim_id or 'contract'}|{message}".encode()).hexdigest()[
        :12
    ]
    return ContractViolation(
        violation_id=f"VIOLATION-{digest.upper()}",
        rule_id=rule_id,
        severity=severity,
        claim_id=claim_id,
        message=message,
        blocks_release=rule_class == ContractRuleClass.blocking,
        suggested_resolution=resolution,
        rule_class=rule_class,
        evidence_span_ids=evidence_span_ids or [],
    )


def verify_exact_source_spans(
    contract: EvidenceContract, context: ContractVerificationContext
) -> list[ContractViolation]:
    violations: list[ContractViolation] = []
    for claim in contract.claims:
        if not claim.supported:
            violations.append(
                _violation(
                    "EC-001",
                    "A ledger claim is marked unsupported.",
                    "Remove the claim or attach exact supporting source evidence.",
                    claim_id=claim.claim_id,
                )
            )
        for span in claim.source_spans:
            record = context.records.get(span.record_id)
            matches = (
                record is not None
                and span.source_document_id in {None, span.record_id}
                and 0 <= span.start <= span.end <= len(record.text)
                and record.text[span.start : span.end] == span.quote
                and span.text == span.quote
                and span.valid
                and span.validation_status in {"unvalidated", "valid"}
                and (span.content_hash is None or span.content_hash == _span_content_hash(span))
            )
            if not matches:
                violations.append(
                    _violation(
                        "EC-001",
                        "A cited source span does not match immutable source text at its declared offsets.",
                        "Correct the record ID, quote, and offsets before release.",
                        claim_id=claim.claim_id,
                    )
                )
                break
    return violations


def verify_source_ownership(
    contract: EvidenceContract, context: ContractVerificationContext
) -> list[ContractViolation]:
    violations: list[ContractViolation] = []
    for claim in contract.claims:
        span_records = {span.record_id for span in claim.source_spans}
        declared_records = set(claim.source_record_ids)
        if (
            (claim.case_id is not None and claim.case_id != contract.case_id)
            or not span_records <= declared_records
            or not declared_records <= set(context.records)
        ):
            violations.append(
                _violation(
                    "EC-002",
                    "A claim cites evidence outside its declared source ownership boundary.",
                    "Declare every cited record and remove references to unknown records.",
                    claim_id=claim.claim_id,
                    evidence_span_ids=[span.span_id for span in claim.source_spans],
                )
            )
    return violations


def verify_claim_provenance(
    contract: EvidenceContract, _context: ContractVerificationContext
) -> list[ContractViolation]:
    allowed_nodes = {
        ClaimType.extracted_fact: "extract",
        ClaimType.normalized_representation: "normalize",
        ClaimType.timeline_interpretation: "timeline",
        ClaimType.compatibility_claim: "hypothesis",
        ClaimType.contradiction_claim: "prosecutor",
        ClaimType.rival_comparison_claim: "rivals",
    }
    return [
        _violation(
            "EC-003",
            "A claim lacks valid node provenance for its claim type.",
            "Regenerate the claim from the declared workflow node.",
            claim_id=claim.claim_id,
        )
        for claim in contract.claims
        if claim.generated_by_node != allowed_nodes[claim.claim_type]
        or not claim.created_by
        or not claim.transformation_version
    ]


def verify_transformation_lineage(
    contract: EvidenceContract, _context: ContractVerificationContext
) -> list[ContractViolation]:
    claim_ids = {claim.claim_id for claim in contract.claims}
    violations: list[ContractViolation] = []
    for claim in contract.claims:
        derived = claim.claim_type != ClaimType.extracted_fact
        invalid_parent = any(parent not in claim_ids for parent in claim.parent_claim_ids)
        if (
            (derived and not claim.parent_claim_ids)
            or invalid_parent
            or (derived and not claim.claim_hash)
        ):
            violations.append(
                _violation(
                    "EC-004",
                    "A derived claim has an incomplete or unverifiable transformation lineage.",
                    "Attach valid parent claim IDs, a transformation version, and a claim hash.",
                    claim_id=claim.claim_id,
                )
            )
    return violations


def verify_normalization_support(
    contract: EvidenceContract, _context: ContractVerificationContext
) -> list[ContractViolation]:
    return [
        _violation(
            "EC-005",
            "A normalized representation is not linked to both source evidence and an extracted parent.",
            "Retain the original extracted claim and exact source span as normalization inputs.",
            claim_id=claim.claim_id,
        )
        for claim in contract.claims
        if claim.claim_type == ClaimType.normalized_representation
        and (not claim.source_spans or not claim.parent_claim_ids)
    ]


def verify_certainty_preservation(
    contract: EvidenceContract, _context: ContractVerificationContext
) -> list[ContractViolation]:
    violations: list[ContractViolation] = []
    claim_by_id = {claim.claim_id: claim for claim in contract.claims}
    certainty_rank = {
        Certainty.missing: 0,
        Certainty.inferred: 1,
        Certainty.estimated: 2,
        Certainty.translated: 2,
        Certainty.exact: 3,
    }
    for claim in contract.claims:
        for span in claim.source_spans:
            declared = claim.certainty_basis.get(span.span_id)
            if declared != span.certainty:
                violations.append(
                    _violation(
                        "EC-006",
                        "A claim does not preserve the certainty label of its cited evidence.",
                        "Carry the source certainty into the claim without promotion.",
                        claim_id=claim.claim_id,
                    )
                )
                break
        if claim.parent_claim_ids:
            parent_certainties = [
                claim_by_id[parent_id].certainty_category
                for parent_id in claim.parent_claim_ids
                if parent_id in claim_by_id
            ]
            if parent_certainties and certainty_rank[claim.certainty_category] > min(
                certainty_rank[item] for item in parent_certainties
            ):
                violations.append(
                    _violation(
                        "EC-006",
                        "A transformation silently increased certainty beyond its least-certain parent.",
                        "Lower the derived certainty or obtain additional exact evidence.",
                        claim_id=claim.claim_id,
                    )
                )
    return violations


def verify_contradiction_coverage(
    contract: EvidenceContract, context: ContractVerificationContext
) -> list[ContractViolation]:
    considered = set(contract.contradictions_considered)
    missing_from_contract = context.hard_conflict_ids - considered
    missing_from_routing = context.hard_conflict_ids - context.routing_hard_conflict_ids
    material_unresolved = bool(context.hard_conflict_ids and context.block_hard_conflicts)
    if not missing_from_contract and not missing_from_routing and not material_unresolved:
        return []
    return [
        _violation(
            "EC-007",
            (
                "A material contradiction remains unresolved and the incident policy fails closed."
                if material_unresolved
                else "One or more hard contradictions are absent from the contract or review-routing input."
            ),
            "Route the exact conflicting spans to authorized review and request resolving evidence.",
            evidence_span_ids=sorted(
                {
                    span_id
                    for claim in contract.claims
                    if claim.claim_type == ClaimType.contradiction_claim
                    for span_id in claim.source_span_ids
                }
            ),
        )
    ]


def verify_rival_coverage(
    contract: EvidenceContract, context: ContractVerificationContext
) -> list[ContractViolation]:
    if contract.classification != Classification.strong_candidate_for_review:
        return []
    if context.close_rival_record_ids <= set(contract.rivals_considered):
        return []
    return [
        _violation(
            "EC-008",
            "A strong review classification lacks analysis for one or more close rivals.",
            "Run the rival-candidate node and include every close rival before release.",
        )
    ]


def verify_workflow_completeness(
    _contract: EvidenceContract, context: ContractVerificationContext
) -> list[ContractViolation]:
    if context.workflow_node_ids is None or context.workflow_node_ids == REQUIRED_WORKFLOW_NODES:
        return []
    return [
        _violation(
            "EC-009",
            "The release candidate was not produced by the complete ordered workflow.",
            "Rerun all 12 protected workflow nodes in registry order.",
        )
    ]


def verify_injection_boundary(
    contract: EvidenceContract, _context: ContractVerificationContext
) -> list[ContractViolation]:
    affected = [
        claim
        for claim in contract.claims
        if any(span.extraction_status == "quarantined" for span in claim.source_spans)
    ]
    return [
        _violation(
            "EC-010",
            "Quarantined instruction content crossed into a decision claim.",
            "Remove the quarantined span from decision evidence and rerun downstream stages.",
            claim_id=claim.claim_id,
            evidence_span_ids=[
                span.span_id
                for span in claim.source_spans
                if span.extraction_status == "quarantined"
            ],
        )
        for claim in affected
    ]


def _normalized_output_text(value: Any) -> str:
    serialized = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).lower()
    return re.sub(r"[^a-z0-9]+", "_", serialized)


def sanitize_forbidden_release_language(value: Any) -> Any:
    """Scrub prohibited wording from a fail-closed reviewer response after verification."""
    if isinstance(value, str):
        sanitized = value
        for phrase in FORBIDDEN_RELEASE_PHRASES:
            parts = phrase.split("_")
            pattern = r"[\W_]+".join(re.escape(part) for part in parts)
            sanitized = re.sub(
                pattern,
                WITHHELD_LANGUAGE_MARKER,
                sanitized,
                flags=re.IGNORECASE,
            )
        return sanitized
    if isinstance(value, list):
        return [sanitize_forbidden_release_language(item) for item in value]
    if isinstance(value, dict):
        return {key: sanitize_forbidden_release_language(item) for key, item in value.items()}
    return value


def verify_forbidden_language(
    contract: EvidenceContract, context: ContractVerificationContext
) -> list[ContractViolation]:
    output_text = _normalized_output_text(
        {
            "candidate_output": context.candidate_output,
            "claims": [claim.model_dump(mode="json") for claim in contract.claims],
        }
    )
    if not any(phrase in output_text for phrase in FORBIDDEN_RELEASE_PHRASES):
        return []
    return [
        _violation(
            "EC-011",
            "Candidate output contains prohibited autonomous-outcome language.",
            "Remove the prohibited language and rerun contract verification.",
        )
    ]


def verify_classification_consistency(
    contract: EvidenceContract, context: ContractVerificationContext
) -> list[ContractViolation]:
    candidate = context.candidate
    if candidate is None:
        return []
    hard_conflict = bool(context.hard_conflict_ids)
    policy_blocks_conflict = hard_conflict and context.block_hard_conflicts
    inconsistent = candidate.classification_code != contract.classification or (
        hard_conflict and contract.classification != Classification.conflicting_evidence
    )
    if not inconsistent and not policy_blocks_conflict:
        return []
    return [
        _violation(
            "EC-012",
            "The classification is inconsistent with deterministic routing inputs or violates the configured hard-conflict release policy.",
            "Recompute classification or resolve the hard conflict under the configured incident policy.",
        )
    ]


def verify_abstention_enforcement(
    contract: EvidenceContract, context: ContractVerificationContext
) -> list[ContractViolation]:
    candidate = context.candidate
    if (
        candidate is None
        or contract.classification != Classification.insufficient_evidence
        or candidate.candidate_id == "NO-CANDIDATE"
        or candidate.abstention_reasons
    ):
        return []
    return [
        _violation(
            "EC-013",
            "An insufficient-evidence outcome lacks an explicit abstention basis.",
            "Record the observable missing or ambiguous evidence that caused abstention.",
        )
    ]


def verify_audit_integrity(
    _contract: EvidenceContract, context: ContractVerificationContext
) -> list[ContractViolation]:
    if context.audit_integrity is None:
        return []
    if (
        context.audit_integrity.valid
        and context.audit_integrity.status == AuditIntegrityStatus.verified
    ):
        return []
    return [
        _violation(
            "EC-014",
            "The authoritative audit chain is broken, incomplete, or unverifiable.",
            "Inspect the first invalid sequence and restore a verified append-only event chain.",
        )
    ]


def verify_replay_integrity(
    _contract: EvidenceContract, context: ContractVerificationContext
) -> list[ContractViolation]:
    if context.replay_status in {None, "exact_match", "equivalent_match"}:
        return []
    return [
        _violation(
            "EC-015",
            "A completed replay diverged or could not be verified.",
            "Resolve the earliest replay checkpoint divergence before release.",
        )
    ]


def verify_evidence_diversity(
    contract: EvidenceContract, _context: ContractVerificationContext
) -> list[ContractViolation]:
    positive = contract.classification == Classification.strong_candidate_for_review
    sources = {record_id for claim in contract.claims for record_id in claim.source_record_ids}
    if not positive or len(sources) >= 2:
        return []
    return [
        _violation(
            "EC-016",
            "The candidate relies on fewer than two source records.",
            "Obtain an independent source before treating this as a clean contract pass.",
            rule_class=ContractRuleClass.review_required,
            severity=ContractSeverity.warning,
        )
    ]


def verify_decision_critical_analysis(
    contract: EvidenceContract, _context: ContractVerificationContext
) -> list[ContractViolation]:
    if (
        contract.classification != Classification.strong_candidate_for_review
        or contract.decision_critical_evidence
    ):
        return []
    return [
        _violation(
            "EC-017",
            "A strong review classification has not yet completed evidence-ablation analysis.",
            "Run at least one deterministic counterfactual over material supporting evidence.",
            rule_class=ContractRuleClass.review_required,
            severity=ContractSeverity.warning,
        )
    ]


def verify_safety_notice(
    contract: EvidenceContract, _context: ContractVerificationContext
) -> list[ContractViolation]:
    if contract.safety_notice == SAFETY_NOTICE:
        return []
    return [
        _violation(
            "EC-018",
            "The mandatory candidate-review safety notice is missing or altered.",
            "Restore the exact mandatory safety notice before release.",
        )
    ]


CONTRACT_RULES = (
    verify_exact_source_spans,
    verify_source_ownership,
    verify_claim_provenance,
    verify_transformation_lineage,
    verify_normalization_support,
    verify_certainty_preservation,
    verify_contradiction_coverage,
    verify_rival_coverage,
    verify_workflow_completeness,
    verify_injection_boundary,
    verify_forbidden_language,
    verify_classification_consistency,
    verify_abstention_enforcement,
    verify_audit_integrity,
    verify_replay_integrity,
    verify_evidence_diversity,
    verify_decision_critical_analysis,
    verify_safety_notice,
)

RULE_METADATA: dict[str, tuple[ContractRuleClass, ContractSeverity, str, str]] = {
    f"EC-{index:03d}": (
        ContractRuleClass.blocking,
        ContractSeverity.critical,
        "The deterministic evidence-contract rule completed without a release-blocking finding.",
        "No remediation is required.",
    )
    for index in range(1, 19)
}
RULE_METADATA["EC-016"] = (
    ContractRuleClass.review_required,
    ContractSeverity.warning,
    "The contract evaluated independent source diversity.",
    "Obtain an independent source when the rule reports a review requirement.",
)
RULE_METADATA["EC-017"] = (
    ContractRuleClass.review_required,
    ContractSeverity.warning,
    "The contract evaluated decision-critical evidence coverage.",
    "Run deterministic evidence ablation when the rule reports a review requirement.",
)

CANONICAL_RULES: tuple[
    tuple[str, tuple[str, ...], ContractRuleClass, ContractSeverity, str, str], ...
] = (
    (
        "SOURCE_SPAN_INTEGRITY",
        ("EC-001", "EC-002"),
        ContractRuleClass.blocking,
        ContractSeverity.critical,
        "Every citation resolves to immutable source text at exact offsets.",
        "Repair the source document, offsets, quotation, or validation hash.",
    ),
    (
        "CLAIM_LINEAGE_COMPLETE",
        ("EC-003", "EC-004", "EC-005"),
        ContractRuleClass.blocking,
        ContractSeverity.critical,
        "Every derived claim retains an extracted parent and transformation record.",
        "Restore the missing parent claim or transformation record.",
    ),
    (
        "CERTAINTY_PRESERVED",
        ("EC-006",),
        ContractRuleClass.blocking,
        ContractSeverity.critical,
        "Transformations preserve or reduce source certainty.",
        "Remove any silent certainty promotion.",
    ),
    (
        "TIMELINE_CONSISTENCY",
        ("EC-012",),
        ContractRuleClass.blocking,
        ContractSeverity.critical,
        "Timeline and routing claims are consistent with deterministic inputs.",
        "Resolve the timeline conflict or record it as material.",
    ),
    (
        "MATERIAL_CONTRADICTIONS_RESOLVED",
        ("EC-007",),
        ContractRuleClass.blocking,
        ContractSeverity.critical,
        "No unresolved material contradiction remains outside the release gate.",
        "Compare the exact conflicting spans and request resolving evidence.",
    ),
    (
        "RIVAL_EXPLANATION_COVERAGE",
        ("EC-008", "EC-016"),
        ContractRuleClass.blocking,
        ContractSeverity.critical,
        "Close rival explanations remain independently inspectable.",
        "Add the missing rival comparison or independent source.",
    ),
    (
        "REQUIRED_SAFETY_NOTICE_PRESENT",
        ("EC-018",),
        ContractRuleClass.blocking,
        ContractSeverity.critical,
        "The mandatory human-led safety boundary is present.",
        "Restore the canonical safety notice.",
    ),
    (
        "HUMAN_REVIEW_ROUTING_VALID",
        ("EC-009", "EC-013", "EC-017"),
        ContractRuleClass.blocking,
        ContractSeverity.critical,
        "The complete workflow routes uncertainty to authorized review.",
        "Complete the protected workflow and review-routing inputs.",
    ),
    (
        "AUDIT_EVENT_READY",
        ("EC-014", "EC-015"),
        ContractRuleClass.blocking,
        ContractSeverity.critical,
        "The append-only audit and replay evidence are ready.",
        "Repair the audit chain or replay divergence.",
    ),
    (
        "RELEASE_AUTHORIZATION_VALID",
        ("EC-010", "EC-011"),
        ContractRuleClass.blocking,
        ContractSeverity.critical,
        "No prohibited autonomous decision or quarantined content enters the release path.",
        "Remove prohibited output and require an authorized disposition.",
    ),
)


def verify_evidence_contract(
    contract: EvidenceContract, context: ContractVerificationContext
) -> EvidenceContract:
    verified = contract.model_copy(deep=True)
    violations_by_rule: dict[str, list[ContractViolation]] = {
        f"EC-{index:03d}": [] for index in range(1, 19)
    }
    for rule in CONTRACT_RULES:
        for violation in rule(verified, context):
            violations_by_rule[violation.rule_id].append(violation)
    violations = [item for values in violations_by_rule.values() for item in values]
    verified.violations = violations
    verified.rule_results = []
    for rule_name, legacy_ids, rule_class, severity, explanation, remediation in CANONICAL_RULES:
        rule_violations = [
            violation for legacy_id in legacy_ids for violation in violations_by_rule[legacy_id]
        ]
        has_block = any(item.blocks_release for item in rule_violations)
        has_warning = any(
            item.rule_class == ContractRuleClass.review_required for item in rule_violations
        )
        status = (
            RuleEvaluationStatus.block
            if has_block
            else RuleEvaluationStatus.warn
            if has_warning
            else RuleEvaluationStatus.pass_
        )
        verified.rule_results.append(
            ContractRuleResult(
                rule_id=rule_name,
                rule_class=rule_class,
                severity=severity,
                passed=not rule_violations,
                affected_claim_ids=sorted(
                    {item.claim_id for item in rule_violations if item.claim_id}
                ),
                affected_evidence_span_ids=sorted(
                    {span_id for item in rule_violations for span_id in item.evidence_span_ids}
                ),
                operator_explanation=(
                    rule_violations[0].message if rule_violations else explanation
                ),
                remediation_guidance=(
                    rule_violations[0].suggested_resolution if rule_violations else remediation
                ),
                rule_name=rule_name,
                rule_version=CANONICAL_RULE_VERSION,
                status=status,
                reason_code=(
                    f"{rule_name}_BLOCKED"
                    if has_block
                    else f"{rule_name}_WARNING"
                    if has_warning
                    else f"{rule_name}_SATISFIED"
                ),
                input_artifact_ids=sorted(
                    {item.claim_id for item in rule_violations if item.claim_id is not None}
                ),
                related_source_span_ids=sorted(
                    {span_id for item in rule_violations for span_id in item.evidence_span_ids}
                ),
                evaluation_timestamp=verified.created_at,
                evaluator_version=VERIFIER_VERSION,
            )
        )
    violations_by_claim: dict[str, list[str]] = {}
    for violation in violations:
        if violation.claim_id:
            violations_by_claim.setdefault(violation.claim_id, []).append(violation.violation_id)
    for claim in verified.claims:
        claim.violations = violations_by_claim.get(claim.claim_id, [])
        claim.consumed_by_rule_ids = sorted(
            {
                result.rule_id
                for result in verified.rule_results
                if (
                    claim.claim_id in result.affected_claim_ids
                    or any(
                        span_id in result.related_source_span_ids
                        for span_id in claim.source_span_ids
                    )
                    or result.rule_id
                    in {
                        "SOURCE_SPAN_INTEGRITY",
                        "CLAIM_LINEAGE_COMPLETE",
                        "CERTAINTY_PRESERVED",
                        "REQUIRED_SAFETY_NOTICE_PRESENT",
                    }
                )
            }
        )
    if any(violation.blocks_release for violation in violations):
        verified.contract_status = ContractStatus.blocked
        verified.release_allowed = False
        verified.classification = None
    elif any(violation.rule_class == ContractRuleClass.review_required for violation in violations):
        verified.contract_status = ContractStatus.passed_with_review_requirements
        verified.release_allowed = True
    else:
        verified.contract_status = ContractStatus.passed
        verified.release_allowed = True
    verified.candidate_ledger = CandidateClaimLedger(
        ledger_id=f"LEDGER-{verified.contract_id.removeprefix('CONTRACT-')}",
        case_id=verified.case_id,
        candidate_id=verified.candidate_id,
        supporting_claim_ids=[
            claim.claim_id
            for claim in verified.claims
            if claim.supported
            and claim.claim_type
            in {
                ClaimType.extracted_fact,
                ClaimType.normalized_representation,
                ClaimType.compatibility_claim,
            }
        ],
        contradiction_claim_ids=[
            claim.claim_id
            for claim in verified.claims
            if claim.claim_type == ClaimType.contradiction_claim
        ],
        timeline_claim_ids=[
            claim.claim_id
            for claim in verified.claims
            if claim.claim_type == ClaimType.timeline_interpretation
        ],
        compatibility_claim_ids=[
            claim.claim_id
            for claim in verified.claims
            if claim.claim_type == ClaimType.compatibility_claim
        ],
        rival_comparison_claim_ids=[
            claim.claim_id
            for claim in verified.claims
            if claim.claim_type == ClaimType.rival_comparison_claim
        ],
        missing_evidence=(
            ["Resolving evidence for the material contradiction is absent."]
            if any(item.rule_id == "EC-007" for item in verified.violations)
            else []
        ),
        required_follow_up_evidence=(
            [
                "Obtain independent source evidence that resolves the material contradiction."
            ]
            if any(item.rule_id == "EC-007" for item in verified.violations)
            else []
        ),
        safety_notices=[verified.safety_notice],
        contract_result_ids=[result.rule_id for result in verified.rule_results],
    )
    return verified


def _claim_id(candidate_id: str, claim_type: ClaimType, discriminator: str) -> str:
    digest = hashlib.sha256(
        f"{candidate_id}|{claim_type.value}|{discriminator}".encode()
    ).hexdigest()[:12]
    return f"CLAIM-{digest.upper()}"


def _span_content_hash(span: EvidenceSpan) -> str:
    """Hash the immutable source citation, excluding mutable validation annotations."""
    return canonical_sha256(
        {
            "source_document_id": span.source_document_id or span.record_id,
            "start": span.start,
            "end": span.end,
            "quotation": span.quote,
            "language": span.language,
        }
    )


def _enrich_span(
    span: EvidenceSpan, source: RecordInput | None, created_at: datetime
) -> EvidenceSpan:
    enriched = span.model_copy(deep=True)
    enriched.source_document_id = enriched.record_id
    enriched.language = source.language if source else None
    enriched.created_at = source.created_at if source and source.created_at else created_at
    enriched.validated_at = created_at
    exact = bool(
        source
        and 0 <= enriched.start <= enriched.end <= len(source.text)
        and source.text[enriched.start : enriched.end] == enriched.quote == enriched.text
        and enriched.valid
    )
    enriched.validation_status = "valid" if exact else "invalid"
    enriched.content_hash = _span_content_hash(enriched)
    return enriched


def _span_support(span: EvidenceSpan, source: RecordInput | None) -> tuple[bool, str]:
    supported = bool(
        source
        and span.valid
        and 0 <= span.start <= span.end <= len(source.text)
        and source.text[span.start : span.end] == span.quote == span.text
    )
    return (
        supported,
        "Exact quote and offsets resolve to immutable source text."
        if supported
        else "The cited span does not resolve exactly to immutable source text.",
    )


def _certainty_basis(spans: list[EvidenceSpan]) -> dict[str, Certainty]:
    return {span.span_id: span.certainty for span in spans}


def _candidate_claims(
    case_id: str,
    candidate: CandidateConnection,
    records: list[NormalizedRecord],
    source_records: dict[str, RecordInput],
    created_at: datetime,
) -> list[EvidenceClaim]:
    normalized_by_id = {record.record_id: record for record in records}
    span_by_id = {span.span_id: span for record in records for span in record.evidence_spans}
    claims: list[EvidenceClaim] = []
    candidate_record_ids = {candidate.record_a_id, candidate.record_b_id}
    relevant_record_ids = candidate_record_ids | {rival.record_id for rival in candidate.rivals}

    for record_id in sorted(relevant_record_ids):
        record = normalized_by_id.get(record_id)
        if record is None:
            continue
        for span in record.evidence_spans:
            supported, reason = _span_support(span, source_records.get(record_id))
            claims.append(
                EvidenceClaim(
                    claim_id=_claim_id(
                        candidate.candidate_id, ClaimType.extracted_fact, span.span_id
                    ),
                    candidate_id=candidate.candidate_id,
                    claim_type=ClaimType.extracted_fact,
                    claim_text=f"{span.field}: {span.text}",
                    source_record_ids=[record_id],
                    source_spans=[span.model_copy(deep=True)],
                    certainty_basis={span.span_id: span.certainty},
                    generated_by_node="extract",
                    supported=supported,
                    support_reason=reason,
                )
            )
        for field in record.fields:
            if field.normalized_value is None or field.source_span_id is None:
                continue
            source_span = span_by_id.get(field.source_span_id)
            if source_span is None:
                continue
            supported, reason = _span_support(source_span, source_records.get(record_id))
            claims.append(
                EvidenceClaim(
                    claim_id=_claim_id(
                        candidate.candidate_id,
                        ClaimType.normalized_representation,
                        field.field_id,
                    ),
                    candidate_id=candidate.candidate_id,
                    claim_type=ClaimType.normalized_representation,
                    claim_text=f"{field.label}: {field.normalized_value}",
                    source_record_ids=[record_id],
                    source_spans=[source_span.model_copy(deep=True)],
                    certainty_basis={source_span.span_id: source_span.certainty},
                    generated_by_node="normalize",
                    supported=supported,
                    support_reason=(
                        f"{reason} The normalized value is additive and the original is retained."
                    ),
                )
            )

    for factor in candidate.compatibility_factors:
        spans = [
            span_by_id[span_id] for span_id in factor.evidence_span_ids if span_id in span_by_id
        ]
        claims.append(
            EvidenceClaim(
                claim_id=_claim_id(
                    candidate.candidate_id, ClaimType.compatibility_claim, factor.factor_id
                ),
                candidate_id=candidate.candidate_id,
                claim_type=ClaimType.compatibility_claim,
                claim_text=f"{factor.field}: {factor.interpretation}",
                source_record_ids=sorted({span.record_id for span in spans}),
                source_spans=[span.model_copy(deep=True) for span in spans],
                certainty_basis=_certainty_basis(spans),
                generated_by_node="hypothesis",
                supported=all(
                    _span_support(span, source_records.get(span.record_id))[0] for span in spans
                ),
                support_reason="Compatibility uses only cited evidence and preserves uncertainty.",
            )
        )

    timeline = next(
        (component for component in candidate.score_components if component.field == "timeline"),
        None,
    )
    if timeline:
        timeline_spans: list[EvidenceSpan] = []
        for record_id in candidate_record_ids:
            record = normalized_by_id.get(record_id)
            if record is not None:
                timeline_spans.extend(
                    span
                    for span in record.evidence_spans
                    if span.field.lower() in {"time", "timeline", "location"}
                )
        claims.append(
            EvidenceClaim(
                claim_id=_claim_id(
                    candidate.candidate_id, ClaimType.timeline_interpretation, "timeline"
                ),
                candidate_id=candidate.candidate_id,
                claim_type=ClaimType.timeline_interpretation,
                claim_text=timeline.explanation,
                source_record_ids=sorted(candidate_record_ids),
                source_spans=[span.model_copy(deep=True) for span in timeline_spans],
                certainty_basis=_certainty_basis(timeline_spans),
                generated_by_node="timeline",
                supported=all(
                    _span_support(span, source_records.get(span.record_id))[0]
                    for span in timeline_spans
                ),
                support_reason="Produced by the existing deterministic timeline rule from cited time and location spans.",
            )
        )

    for conflict in candidate.conflicts:
        spans = [
            span_by_id[span_id] for span_id in conflict.evidence_span_ids if span_id in span_by_id
        ]
        claims.append(
            EvidenceClaim(
                claim_id=_claim_id(
                    candidate.candidate_id, ClaimType.contradiction_claim, conflict.conflict_id
                ),
                candidate_id=candidate.candidate_id,
                claim_type=ClaimType.contradiction_claim,
                claim_text=conflict.explanation,
                source_record_ids=sorted({span.record_id for span in spans}),
                source_spans=[span.model_copy(deep=True) for span in spans],
                certainty_basis=_certainty_basis(spans),
                generated_by_node="prosecutor",
                supported=all(
                    _span_support(span, source_records.get(span.record_id))[0] for span in spans
                ),
                support_reason="Contradiction remains separately represented with cited evidence.",
            )
        )

    for rival in candidate.rivals:
        rival_record = normalized_by_id.get(rival.record_id)
        spans = rival_record.evidence_spans if rival_record else []
        claims.append(
            EvidenceClaim(
                claim_id=_claim_id(
                    candidate.candidate_id, ClaimType.rival_comparison_claim, rival.record_id
                ),
                candidate_id=candidate.candidate_id,
                claim_type=ClaimType.rival_comparison_claim,
                claim_text=rival.summary,
                source_record_ids=[rival.record_id],
                source_spans=[span.model_copy(deep=True) for span in spans],
                certainty_basis=_certainty_basis(spans),
                generated_by_node="rivals",
                supported=all(
                    _span_support(span, source_records.get(span.record_id))[0] for span in spans
                ),
                support_reason="The existing rival node compared the nearby record on a fixed field set.",
            )
        )
    extracted_by_span = {
        claim.source_spans[0].span_id: claim.claim_id
        for claim in claims
        if claim.claim_type == ClaimType.extracted_fact and claim.source_spans
    }
    extracted_by_record: dict[str, list[str]] = {}
    for claim in claims:
        if claim.claim_type == ClaimType.extracted_fact:
            for record_id in claim.source_record_ids:
                extracted_by_record.setdefault(record_id, []).append(claim.claim_id)
    transformation_types = {
        ClaimType.extracted_fact: "direct_extraction",
        ClaimType.normalized_representation: "additive_normalization",
        ClaimType.timeline_interpretation: "deterministic_timeline",
        ClaimType.compatibility_claim: "deterministic_compatibility",
        ClaimType.contradiction_claim: "structured_contradiction",
        ClaimType.rival_comparison_claim: "deterministic_rival_comparison",
    }
    for claim in claims:
        claim.source_spans = [
            _enrich_span(span, source_records.get(span.record_id), created_at)
            for span in claim.source_spans
        ]
        claim.source_record_id = (
            claim.source_record_ids[0] if len(claim.source_record_ids) == 1 else None
        )
        claim.source_span_ids = [span.span_id for span in claim.source_spans]
        claim.transformation_type = transformation_types[claim.claim_type]
        claim.created_at = created_at
        claim.case_id = case_id
        claim.raw_value = " | ".join(span.quote for span in claim.source_spans) or claim.claim_text
        claim.normalized_value = claim.claim_text
        claim.certainty_category = min(
            (span.certainty for span in claim.source_spans),
            key=lambda item: {
                Certainty.missing: 0,
                Certainty.inferred: 1,
                Certainty.estimated: 2,
                Certainty.translated: 2,
                Certainty.exact: 3,
            }[item],
            default=Certainty.inferred,
        )
        if claim.claim_type != ClaimType.extracted_fact:
            parents = {
                extracted_by_span[span_id]
                for span_id in claim.source_span_ids
                if span_id in extracted_by_span
            }
            if not parents:
                parents = {
                    parent
                    for record_id in claim.source_record_ids
                    for parent in extracted_by_record.get(record_id, [])[:1]
                }
            claim.parent_claim_ids = sorted(parents)
            claim.transformation_history = [
                ClaimTransformation(
                    transformation_id=f"TRANSFORM-{claim.claim_id.removeprefix('CLAIM-')}",
                    transformation_type=claim.transformation_type,
                    transformation_version=claim.transformation_version,
                    input_claim_ids=claim.parent_claim_ids,
                    input_artifact_ids=claim.source_span_ids,
                    output_certainty=claim.certainty_category,
                    created_by_step=claim.generated_by_node,
                    created_at=created_at,
                )
            ]
        claim.claim_hash = canonical_sha256(
            claim.model_dump(mode="python", exclude={"claim_hash", "violations"})
        )
    return claims


def _close_rival_record_ids(
    candidate: CandidateConnection, candidates: list[CandidateConnection]
) -> set[str]:
    primary_records = {candidate.record_a_id, candidate.record_b_id}
    close: set[str] = set()
    for other in candidates:
        if other.candidate_id == candidate.candidate_id:
            continue
        other_records = {other.record_a_id, other.record_b_id}
        if primary_records.isdisjoint(other_records):
            continue
        if abs(candidate.retrieval_score - other.retrieval_score) <= 0.15:
            close.update(other_records - primary_records)
    return close


def _base_contract(
    *,
    contract_id: str,
    case_id: str,
    candidate_id: str,
    classification: Classification,
    claims: list[EvidenceClaim],
    contradictions: list[str],
    rivals: list[str],
    created_at: datetime,
) -> EvidenceContract:
    return EvidenceContract(
        contract_id=contract_id,
        case_id=case_id,
        candidate_id=candidate_id,
        classification=classification,
        contract_status=ContractStatus.blocked,
        release_allowed=False,
        claims=claims,
        violations=[],
        contradictions_considered=contradictions,
        rivals_considered=rivals,
        decision_critical_evidence=[],
        audit_chain_status={},
        created_at=created_at,
        verifier_version=VERIFIER_VERSION,
        rule_set_version=RULE_SET_VERSION,
        safety_notice=SAFETY_NOTICE,
    )


def _contract_id(case_id: str, candidate_id: str) -> str:
    digest = hashlib.sha256(f"{case_id}|{candidate_id}|{VERIFIER_VERSION}".encode()).hexdigest()
    return f"CONTRACT-{digest[:16].upper()}"


def build_evidence_contracts(
    *,
    case_id: str,
    candidates: list[CandidateConnection],
    records: list[NormalizedRecord],
    source_records: list[RecordInput],
    review_routing_inputs: dict[str, dict[str, list[str]]],
    created_at: datetime,
    workflow_node_ids: tuple[str, ...] | None = None,
    audit_integrity: AuditIntegrityResult | None = None,
    replay_status: str | None = None,
    block_hard_conflicts: bool = False,
) -> list[EvidenceContract]:
    source_by_id = {record.record_id: record for record in source_records}
    contracts: list[EvidenceContract] = []
    candidate_set = candidates or [
        CandidateConnection(
            candidate_id="NO-CANDIDATE",
            record_a_id=source_records[0].record_id,
            record_b_id=source_records[0].record_id,
            label="Insufficient evidence",
            classification="Insufficient evidence",
            classification_code=Classification.insufficient_evidence,
            supporting_summary="No candidate pair was available.",
            opposing_summary="Available evidence was insufficient.",
            verification_question="Can an authorized reviewer obtain additional records?",
            verification_explanation="Additional source evidence may enable a future review.",
            retrieval_score=0,
            rank=1,
        )
    ]
    response_record_payload = [record.model_dump(mode="json") for record in records]
    for candidate in candidate_set:
        classification = candidate.classification_code or Classification.insufficient_evidence
        claims = (
            _candidate_claims(case_id, candidate, records, source_by_id, created_at)
            if candidate.candidate_id != "NO-CANDIDATE"
            else []
        )
        hard_conflicts = [
            conflict.conflict_id for conflict in candidate.conflicts if conflict.severity == "hard"
        ]
        rivals = [rival.record_id for rival in candidate.rivals]
        contract = _base_contract(
            contract_id=_contract_id(case_id, candidate.candidate_id),
            case_id=case_id,
            candidate_id=candidate.candidate_id,
            classification=classification,
            claims=claims,
            contradictions=hard_conflicts,
            rivals=rivals,
            created_at=created_at,
        )
        routing = review_routing_inputs.get(candidate.candidate_id, {})
        context = ContractVerificationContext(
            records=source_by_id,
            hard_conflict_ids=set(hard_conflicts),
            routing_hard_conflict_ids=set(routing.get("hard_conflict_ids", [])),
            close_rival_record_ids=_close_rival_record_ids(candidate, candidates),
            candidate_output={
                "candidate": candidate.model_dump(mode="json"),
                "records": response_record_payload,
            },
            candidate=candidate,
            workflow_node_ids=workflow_node_ids,
            audit_integrity=audit_integrity,
            replay_status=replay_status,
            block_hard_conflicts=block_hard_conflicts,
        )
        try:
            contracts.append(verify_evidence_contract(contract, context))
        except Exception:
            contract.contract_status = ContractStatus.verifier_error
            contract.release_allowed = False
            contract.classification = None
            contract.violations = [
                _violation(
                    "EC-000",
                    "The deterministic contract verifier could not complete.",
                    "Inspect verifier logs and rerun; do not release this output.",
                )
            ]
            contracts.append(contract)
    return contracts


def build_release_view(response: AnalyzeResponse) -> AnalyzeResponse:
    """Return the fail-closed API/persistence view without mutating internal evidence."""
    gated = response.model_copy(deep=True)
    contracts = {item.candidate_id: item for item in gated.evidence_contracts}
    aggregate_withheld = gated.contract_release_status != ContractReleaseStatus.released
    for candidate in gated.candidates:
        contract = contracts.get(candidate.candidate_id)
        candidate.classification = None
        candidate.classification_code = None
        if aggregate_withheld or contract is None or not contract.release_allowed:
            candidate.label = "Output withheld"
            candidate.supporting_summary = "Decision-facing output withheld by evidence contract."
            candidate.opposing_summary = (
                "Inspect cited evidence, blocking rules, and required authorized review."
            )
            candidate.linkage_decision = None
            candidate.linkage_decision_state = None
            candidate.retrieval_score = None
            candidate.rank = None
            candidate.score_components = []
            candidate.review_priority = None
            candidate.llm_downgrade_applied = False
            candidate.llm_downgrade_reason = None
    return gated
