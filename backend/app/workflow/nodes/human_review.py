"""
Human Review Router Node — node 12 of the THREADLINE workflow.

Routes candidate packets to authorized human review with structured
priority levels and exact reason codes. Never performs autonomous
identity determination.

Humanitarian safety principle: all outputs go to human review; the
system merely structures the queue. No autonomous identity decision.
"""

from app.schemas.linkage import LinkageDecisionState
from app.schemas.models import Classification, ValidationResult
from app.workflow.base import NodeOutcome, WorkflowNode
from app.workflow.context import WorkflowContext

REVIEW_PRIORITY_LABELS = {
    "urgent_conflict_review": "URGENT: Conflicting evidence requires immediate authorized review.",
    "high_priority_verification": "HIGH: Recommended linkage awaiting authorized verification.",
    "standard_verification": "STANDARD: Ambiguous candidate requires authorized comparison.",
    "request_more_information": "INFO_REQUEST: Insufficient evidence; request additional information.",
    "no_action_recommended": "NO_ACTION: System recommends against linkage.",
    "technical_failure": "TECHNICAL: System error; escalate to administrator.",
}


class HumanReviewRouterNode(WorkflowNode):
    node_id, order = "review", 12
    name, short_name = "Human-review router", "Human review"
    category, purpose = (
        "Human decision",
        "Route candidate packets with structured priority levels and exact reason codes.",
    )
    uses_llm, requires_human_input, can_disable = False, True, False
    input_schema, output_schema = "PrivacySafePacket", "HumanReviewRoute"
    failure_condition = (
        "An output implies autonomous identity determination or bypasses authorized review."
    )
    constraints = (
        "No final identity decision",
        "Authorized review required",
        "Abstention retained",
        "Structured review priorities",
        "Exact unresolved issues exposed",
    )

    async def run(self, context: WorkflowContext) -> NodeOutcome:
        review_queue = []

        for candidate in context.candidates:
            decision = context.linkage_decisions.get(candidate.candidate_id)
            priority = candidate.review_priority or "standard_verification"
            priority_label = REVIEW_PRIORITY_LABELS.get(priority, REVIEW_PRIORITY_LABELS["standard_verification"])

            # Build structured review packet
            packet = {
                "candidate_id": candidate.candidate_id,
                "record_a_id": candidate.record_a_id,
                "record_b_id": candidate.record_b_id,
                "priority": priority,
                "priority_label": priority_label,
                "linkage_state": candidate.linkage_decision_state,
                "false_merge_risk": candidate.false_merge_risk,
                "unresolved_issues": (
                    candidate.abstention_reasons
                    if candidate.abstention_reasons
                    else []
                ),
                "strongest_supporting": (
                    [s.field_name for s in decision.strongest_supporting]
                    if decision
                    else []
                ),
                "strongest_conflicts": (
                    [c.field_name for c in decision.strongest_conflicting]
                    if decision
                    else []
                ),
                "blocking_conflicts": (
                    [b.field_name for b in decision.blocking_conflicts]
                    if decision
                    else []
                ),
                "missing_critical_evidence": (
                    [m.field_name for m in decision.missing_critical]
                    if decision
                    else []
                ),
                "rival_candidates": [
                    {
                        "record_id": r.record_id,
                        "display_name": r.display_name,
                        "summary": r.summary,
                    }
                    for r in candidate.rivals
                ],
                "llm_downgrade_applied": candidate.llm_downgrade_applied,
                "llm_downgrade_reason": candidate.llm_downgrade_reason,
                "permitted_actions": _permitted_actions(decision.state if decision else None),
                "safe_next_action": _safe_next_action(priority),
            }
            review_queue.append(packet)

            context.audit.add(
                "human review requested",
                self.name,
                [candidate.record_a_id, candidate.record_b_id],
                (
                    candidate.linkage_decision_state
                    or candidate.classification_code.value
                ),
                f"Priority: {priority}",
                f"THREADLINE does not autonomously determine identity. {priority_label}",
            )

        # Count by priority
        priority_counts = {}
        for pkt in review_queue:
            p = pkt["priority"]
            priority_counts[p] = priority_counts.get(p, 0) + 1

        return NodeOutcome(
            summary=(
                f"Routed {len(review_queue)} candidate(s) to authorized human review "
                f"with structured priorities: {priority_counts}."
            ),
            data={
                "review_required": True,
                "candidate_packets": len(review_queue),
                "review_queue": review_queue,
                "priority_counts": priority_counts,
                "permitted_actions": [
                    "request_more_information",
                    "dismiss_candidate",
                    "escalate_authorized_review",
                    "mark_unrelated",
                    "record_authorized_verification_outcome",
                ],
            },
            validation_results=[
                ValidationResult(
                    check="autonomous_identity_decision_blocked",
                    passed=True,
                    detail="The router exposes no confirm-match action.",
                ),
                ValidationResult(
                    check="structured_priority_routing",
                    passed=True,
                    detail=f"Review queue prioritized: {priority_counts}.",
                ),
            ],
            abstention_reason=(
                "The system refuses to select one candidate; "
                "human investigation may request more information."
                if any(
                    c.classification_code == Classification.insufficient_evidence
                    for c in context.candidates
                )
                else None
            ),
        )


def _permitted_actions(state: LinkageDecisionState | None) -> list[str]:
    """Determine permitted review actions based on linkage state."""
    if state is None:
        return ["request_more_information", "escalate_authorized_review"]
    mapping = {
        LinkageDecisionState.link_recommended: [
            "record_authorized_verification_outcome",
            "escalate_authorized_review",
            "request_more_information",
        ],
        LinkageDecisionState.human_review_required: [
            "request_more_information",
            "escalate_authorized_review",
            "dismiss_candidate",
        ],
        LinkageDecisionState.insufficient_evidence: [
            "request_more_information",
            "dismiss_candidate",
        ],
        LinkageDecisionState.do_not_link: [
            "dismiss_candidate",
            "mark_unrelated",
            "request_more_information",
        ],
        LinkageDecisionState.blocked_by_conflict: [
            "escalate_authorized_review",
            "request_more_information",
        ],
        LinkageDecisionState.system_error: [
            "escalate_authorized_review",
        ],
    }
    return mapping.get(state, ["request_more_information", "escalate_authorized_review"])


def _safe_next_action(priority: str) -> str:
    """Recommend the safest next action for the reviewer."""
    mapping = {
        "urgent_conflict_review": (
            "Resolve the blocking conflict before any linkage determination."
        ),
        "high_priority_verification": (
            "Verify the recommended linkage with an independent authoritative source."
        ),
        "standard_verification": (
            "Compare records using the structured evidence packet."
        ),
        "request_more_information": (
            "Request additional information from field teams or family sources."
        ),
        "no_action_recommended": (
            "No linkage recommended; dismiss or mark unrelated."
        ),
        "technical_failure": (
            "Escalate to system administrator for diagnostic review."
        ),
    }
    return mapping.get(priority, "Review the evidence packet and determine next steps.")
