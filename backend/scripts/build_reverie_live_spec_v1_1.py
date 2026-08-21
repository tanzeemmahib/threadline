"""Supersede the unobserved Reverie v1 draft with the fair citation-capable v1.1 spec."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import cast

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.evaluation.reverie_live import atomic_write_json
from app.schemas.reverie_evaluation import load_frozen_live_evaluation_spec

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = BACKEND_ROOT.parent
V1_PATH = BACKEND_ROOT / "fixtures" / "reverie_live_evaluation_v1.json"
V11_PATH = BACKEND_ROOT / "fixtures" / "reverie_live_evaluation_v1_1.json"
LIVE_OUTPUT = BACKEND_ROOT / "data" / "reverie_live_evaluation_v1_1"
V1_SHA256 = "dccfb17115077a2869f88d00466825bf9b85d3969ae32aabcf2c3e1a5b811c99"

NEW_SOURCE_PINS = {
    "backend/app/baselines/reverie_one_shot.py": (
        "7d2bb2554539f19f960088d0afd8271361202fa118762d32918206c5b75e95bb"
    ),
    "backend/app/evaluation/reverie_live.py": (
        "ed23aff846d9fcdccda34df3f15e4298f096a627807118647c22357295ac40df"
    ),
    "backend/app/schemas/reverie_evaluation.py": (
        "342a5ab22c809603e0259d8509a7818e2adc619978c3e77d25d0bea3ac55b368"
    ),
    "backend/scripts/run_reverie_live_evaluation.py": (
        "fa0f0eaaa93b259737428f8d2d41f01b6a366541b5dae92da870b4101636cf72"
    ),
    "backend/app/services/field_key_normalizer.py": (
        "d19a580512b1ef24a7073d13b6e184bee3d682e47835c3a99cede064f66e45e0"
    ),
}

METRIC_DEFINITIONS = {
    "schema_validity": (
        "Whether the provider response passed the registered strict Pydantic output schema "
        "under the same transport-retry and single-repair policy."
    ),
    "source_span_coverage": (
        "Unique expected record-field pairs supported by an exact valid source span divided "
        "by all expected record-field pairs; identical rule for both systems."
    ),
    "exact_citation_validity": (
        "Emitted non-missing claims whose record exists and whose zero-based source slice "
        "equals the supplied quote, divided by all emitted non-missing claims."
    ),
    "supported_field_count": (
        "Count of unique expected record-field pairs with an exact valid source span; "
        "duplicates do not increase the count."
    ),
    "unsupported_field_count": (
        "Count of unique emitted record-field pairs that are outside the expected field set "
        "or lack an exact valid source span."
    ),
    "identity_outcome": (
        "The actual one-shot classification or deterministic THREADLINE linkage state, "
        "reported without remapping or upgrading."
    ),
    "blocking_conflict_handling": (
        "Whether conflict handling is an independent deterministic release boundary rather "
        "than part of the model recommendation."
    ),
    "auditability": (
        "Availability of validated structured output, sanitized provider-call records, exact "
        "input hashes, workflow trace, evidence contracts, audit chain, and replay manifest."
    ),
    "provider_call_count": "Number of logical provider generations, including repair calls as one logical generation.",
    "transport_attempts": "Number of recorded HTTP attempts, including fallbacks and retries.",
    "latency_ms": "Measured provider duration in milliseconds, reported per system run and summed only descriptively.",
    "token_usage": "Provider-reported total token usage when present; otherwise Not measured.",
}


def build_artifact() -> dict[str, object]:
    _, observed_v1_sha = load_frozen_live_evaluation_spec(
        V1_PATH,
        repository_root=REPOSITORY_ROOT,
    )
    if observed_v1_sha != V1_SHA256:
        raise ValueError("the preserved v1 preregistration draft has changed")
    artifact = json.loads(V1_PATH.read_text("utf-8"))
    artifact["schema_version"] = "threadline-reverie-live-evaluation-spec/1.1.0"
    artifact["spec_id"] = "THREADLINE-REVERIE-LIVE-EVAL-V1.1"
    artifact["frozen_at"] = "2026-08-21T01:23:28.159249Z"
    artifact["supersedes"] = {
        "spec_id": "THREADLINE-REVERIE-LIVE-EVAL-V1",
        "path": "backend/fixtures/reverie_live_evaluation_v1.json",
        "sha256": V1_SHA256,
        "status": "superseded_before_provider_observation",
        "reason": (
            "The draft one-shot requested internal span IDs absent from its input and field "
            "counts were asymmetric. No provider output or result directory existed when "
            "v1.1 replaced it."
        ),
    }

    obsolete = {
        "backend/app/baselines/single_call.py",
        "backend/app/baselines/runner.py",
    }
    source_files = [pin for pin in artifact["source_files"] if pin["path"] not in obsolete]
    paths = {pin["path"] for pin in source_files}
    for path, sha256 in NEW_SOURCE_PINS.items():
        pin = {"path": path, "sha256": sha256}
        if path in paths:
            source_files = [pin if item["path"] == path else item for item in source_files]
        else:
            source_files.append(pin)
    artifact["source_files"] = source_files

    artifact["prompts"] = [
        prompt for prompt in artifact["prompts"] if prompt["template_id"] != "structured_baseline"
    ]
    artifact["prompts"].insert(
        0,
        {
            "template_id": "reverie_one_shot",
            "version": "v1",
            "path": "backend/app/prompts/templates/reverie_one_shot.v1.txt",
            "sha256": "9e073270415face7e5095394024bbb4b91453069a0a3c90d7765398c2ffdbe94",
        },
    )
    artifact["output_schemas"] = [
        schema
        for schema in artifact["output_schemas"]
        if schema["schema_name"] != "SingleCallModelOutput"
    ]
    artifact["output_schemas"].insert(
        0,
        {
            "schema_name": "ReverieOneShotModelOutput",
            "sha256": "c8150964d5d1e8dee5aa772417774f6e696f0a2f27f86ae1d382c6a9647079d0",
        },
    )
    one_shot = next(
        system for system in artifact["systems"] if system["system_id"] == "structured_one_shot"
    )
    one_shot["implementation"] = "app.baselines.reverie_one_shot.run_reverie_one_shot"
    one_shot["prompt_ids"] = ["reverie_one_shot:v1"]
    one_shot["output_schema_names"] = ["ReverieOneShotModelOutput"]

    acceptable = {
        "PROMPT-LAB-CROSS-SCRIPT": [
            "strong_candidate_for_review",
            "possible_candidate",
        ],
        "PROMPT-LAB-SHARED-CONTACT": [
            "possible_candidate",
            "insufficient_evidence",
        ],
        "PROMPT-LAB-BLOCKING-CONFLICT": ["conflicting_evidence"],
    }
    for case in artifact["cases"]:
        case["ground_truth"]["acceptable_one_shot_classifications"] = acceptable[case["case_id"]]

    artifact["metric_definitions"] = METRIC_DEFINITIONS
    artifact["limitations"] = [
        "The v1 preregistration draft was superseded before any provider output was observed; its file and SHA remain preserved.",
        "The provider adapter does not send a seed; temperature zero does not guarantee byte-identical live responses.",
        "The configured model identifier is provider-managed and no immutable provider model revision is exposed.",
        "All cases are synthetic and do not establish operational humanitarian validity or demographic fairness.",
        "One-shot and workflow receive identical records and incident context, but the workflow intentionally makes multiple constrained calls and applies deterministic policy.",
        "Field precision and coverage use the same expected record-field set and exact quote/offset validation for both systems.",
        "A partial run must remain explicitly partial and cannot be published as a completed comparison.",
    ]
    return cast(dict[str, object], artifact)


def _encoded(artifact: dict[str, object]) -> bytes:
    return json.dumps(
        artifact,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ).encode("utf-8")


def check() -> tuple[dict[str, object], str]:
    artifact = build_artifact()
    expected = _encoded(artifact)
    observed = V11_PATH.read_bytes()
    if observed != expected:
        raise ValueError("frozen v1.1 spec bytes differ from the preregistered derivation")
    _spec, digest = load_frozen_live_evaluation_spec(V11_PATH, repository_root=REPOSITORY_ROOT)
    expected_digest = hashlib.sha256(expected).hexdigest()
    if digest != expected_digest:
        raise ValueError("frozen v1.1 spec SHA differs from its derived bytes")
    return artifact, digest


def write() -> tuple[dict[str, object], str]:
    if LIVE_OUTPUT.exists():
        raise ValueError(
            "refusing to regenerate a frozen spec after provider observation; use --check"
        )
    artifact = build_artifact()
    digest = atomic_write_json(V11_PATH, artifact)
    load_frozen_live_evaluation_spec(V11_PATH, repository_root=REPOSITORY_ROOT)
    return artifact, digest


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--write", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    arguments = _arguments()
    built, digest = write() if arguments.write else check()
    print(f"mode={'write' if arguments.write else 'check'}")
    print(f"spec_id={built['spec_id']}")
    print(f"spec_path={V11_PATH}")
    print(f"spec_sha256={digest}")
