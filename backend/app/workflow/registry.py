from app.workflow.base import WorkflowNode
from app.workflow.nodes import (
    CandidateRetrievalNode,
    ContradictionProsecutorNode,
    EvidenceQuarantineNode,
    HumanReviewRouterNode,
    IncidentConfigurationNode,
    IndependentAdjudicationNode,
    MatchHypothesisNode,
    MultilingualNormalizationNode,
    PrivacyGateNode,
    RivalCandidateNode,
    StructuredExtractionNode,
    TimelineReconstructionNode,
)


def workflow_nodes() -> list[WorkflowNode]:
    return [
        IncidentConfigurationNode(),
        EvidenceQuarantineNode(),
        StructuredExtractionNode(),
        MultilingualNormalizationNode(),
        TimelineReconstructionNode(),
        CandidateRetrievalNode(),
        MatchHypothesisNode(),
        ContradictionProsecutorNode(),
        RivalCandidateNode(),
        IndependentAdjudicationNode(),
        PrivacyGateNode(),
        HumanReviewRouterNode(),
    ]


def disableable_node_ids() -> set[str]:
    return {node.node_id for node in workflow_nodes() if node.can_disable}
