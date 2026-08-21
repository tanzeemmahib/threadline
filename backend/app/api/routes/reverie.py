from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.schemas.reverie_artifacts import (
    PromptLabArtifact,
    load_live_evaluation_artifact,
    load_prompt_lab_artifact,
    validate_prompt_lab_artifact,
)
from app.schemas.reverie_evaluation import LiveEvaluationArtifact

router = APIRouter(prefix="/api/v1/reverie", tags=["reverie"])


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[4]


@lru_cache(maxsize=1)
def _prompt_lab_artifact() -> PromptLabArtifact:
    artifact_path = _repository_root() / "docs" / "submission" / "reverie-prompt-lab.json"
    return load_prompt_lab_artifact(artifact_path, repository_root=_repository_root())


@router.get("/prompt-lab", response_model=PromptLabArtifact)
async def prompt_lab() -> PromptLabArtifact:
    """Return the locked synthetic Prompt Lab artifact without executing a provider."""

    try:
        artifact = PromptLabArtifact.model_validate(_prompt_lab_artifact())
        validate_prompt_lab_artifact(artifact, repository_root=_repository_root())
        return artifact.model_copy(deep=True)
    except (OSError, ValueError) as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "error_code": "REVERIE_ARTIFACT_UNAVAILABLE",
                "message": "The locked synthetic Prompt Lab artifact is unavailable or malformed.",
                "retryable": True,
            },
        ) from exc


@router.get("/live-evaluation", response_model=LiveEvaluationArtifact)
async def live_evaluation() -> LiveEvaluationArtifact:
    """Return the validated live comparison, including an explicit partial state."""

    artifact_path = (
        _repository_root() / "backend" / "data" / "reverie_live_evaluation_v1_1" / "results.json"
    )
    if not artifact_path.is_file():
        raise HTTPException(
            status_code=404,
            detail={
                "error_code": "REVERIE_LIVE_EVALUATION_NOT_MEASURED",
                "message": "No validated live same-model comparison artifact is available.",
                "retryable": False,
            },
        )
    try:
        return load_live_evaluation_artifact(artifact_path, repository_root=_repository_root())
    except (OSError, ValueError) as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "error_code": "REVERIE_LIVE_EVALUATION_INVALID",
                "message": "The live comparison artifact failed strict runtime validation.",
                "retryable": False,
            },
        ) from exc
