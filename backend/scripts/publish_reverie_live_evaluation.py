"""Publish a completed, validated live comparison to the submission directory.

The runner's backend artifact remains authoritative. This command creates a
byte-identical judge-facing result plus a small manifest that pins the raw,
credential-free recorder in place without duplicating its potentially large
payload. Partial, failed, drifted, or credential-bearing runs fail closed.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.evaluation.reverie_live import sha256_bytes
from app.schemas.reverie_evaluation import (
    LiveEvaluationArtifact,
    ProviderRecorderCheckpoint,
    load_frozen_live_evaluation_spec,
)

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = BACKEND_ROOT.parent
DEFAULT_RESULTS = BACKEND_ROOT / "data" / "reverie_live_evaluation_v1_1" / "results.json"
DEFAULT_DESTINATION = (
    REPOSITORY_ROOT / "docs" / "submission" / "reverie-live-evaluation-results.json"
)
DEFAULT_MANIFEST = REPOSITORY_ROOT / "docs" / "submission" / "reverie-live-evaluation-manifest.json"


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--destination", type=Path, default=DEFAULT_DESTINATION)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    return parser.parse_args()


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temporary.open("wb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _inside_repository(path: Path) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(REPOSITORY_ROOT)
    except ValueError as exc:
        raise ValueError(f"artifact path escapes repository: {resolved}") from exc
    return resolved


def publish(*, results_path: Path, destination_path: Path, manifest_path: Path) -> dict[str, Any]:
    results_path = _inside_repository(results_path)
    destination_path = _inside_repository(destination_path)
    manifest_path = _inside_repository(manifest_path)
    results_bytes = results_path.read_bytes()
    artifact = LiveEvaluationArtifact.model_validate_json(results_bytes)
    if artifact.status != "complete":
        raise ValueError(f"live comparison is not complete: {artifact.status}")
    if not artifact.same_input_and_config_verified:
        raise ValueError("same-input/configuration proof is not verified")
    if artifact.completed_system_runs != artifact.expected_system_runs:
        raise ValueError("completed system-run count does not equal the frozen expectation")
    if artifact.failed_system_runs:
        raise ValueError("failed system runs cannot be published as a completed comparison")

    spec_path = _inside_repository(REPOSITORY_ROOT / artifact.spec_path)
    spec, spec_sha = load_frozen_live_evaluation_spec(spec_path, repository_root=REPOSITORY_ROOT)
    if spec_sha != artifact.spec_sha256:
        raise ValueError("result spec SHA does not match the validated frozen spec")
    if artifact.spec_id != spec.spec_id or artifact.source_commit != spec.source_commit:
        raise ValueError("result provenance does not match the validated frozen spec")
    expected_runs = spec.schedule.repetitions * len(spec.cases) * len(spec.systems)
    if artifact.expected_system_runs != expected_runs:
        raise ValueError("result expected-run count does not match the frozen schedule")
    expected_case_repetitions = {
        (case.case_id, repetition)
        for case in spec.cases
        for repetition in range(1, spec.schedule.repetitions + 1)
    }
    observed_case_repetitions = {(case.case_id, case.repetition) for case in artifact.cases}
    if observed_case_repetitions != expected_case_repetitions:
        raise ValueError("result cases do not exactly cover the frozen schedule")
    if len(artifact.cases) != len(expected_case_repetitions):
        raise ValueError("result contains duplicate case repetitions")

    recorder_path = _inside_repository(REPOSITORY_ROOT / artifact.recorder_artifact_path)
    recorder_bytes = recorder_path.read_bytes()
    recorder_sha = sha256_bytes(recorder_bytes)
    if recorder_sha != artifact.recorder_artifact_sha256:
        raise ValueError("raw provider recorder SHA drift")
    recorder = ProviderRecorderCheckpoint.model_validate_json(recorder_bytes)
    if recorder.contains_credentials:
        raise ValueError("credential-bearing provider artifacts cannot be published")
    if recorder.spec_sha256 != artifact.spec_sha256:
        raise ValueError("raw provider recorder belongs to a different frozen spec")
    if artifact.provider != recorder.safe_provider_config:
        raise ValueError("result provider configuration differs from the recorder")
    completed_run_ids = {
        run.system_run_id
        for case_repetition in artifact.cases
        for run in case_repetition.systems.values()
        if run.status == "ok"
    }
    superseded_failed_calls: list[str] = []
    for call in recorder.calls.values():
        if call.status == "ok":
            continue
        # A recorded failed logical call is acceptable only when its system run
        # ultimately completed successfully (recovered under the symmetric
        # retry policy). The failed call and its transport history remain fully
        # recorded and are counted explicitly in the publication manifest; they
        # are never removed or relabelled as successful.
        if call.system_run_id not in completed_run_ids:
            raise ValueError(
                f"failed logical call {call.logical_call_id} belongs to a system run "
                "that did not complete successfully"
            )
        if call.error is None:
            raise ValueError(f"failed logical call {call.logical_call_id} has no recorded error")
        superseded_failed_calls.append(call.logical_call_id)
    if any(attempt.status == "in_flight" for attempt in recorder.transport_attempts):
        raise ValueError("raw provider recorder contains in-flight transport attempts")

    recorded_call_ids = set(recorder.calls)
    referenced_call_ids: set[str] = set()
    frozen_cases = {case.case_id: case for case in spec.cases}
    frozen_system_ids = {system.system_id for system in spec.systems}
    for case_repetition in artifact.cases:
        frozen_case = frozen_cases[case_repetition.case_id]
        if case_repetition.input_manifest != frozen_case.input_manifest:
            raise ValueError("case input manifest drift in completed results")
        if set(case_repetition.systems) != frozen_system_ids:
            raise ValueError("case repetition does not contain both frozen systems")
        for system_id, system_run in case_repetition.systems.items():
            expected_run_id = (
                f"REP-{case_repetition.repetition:02d}:{case_repetition.case_id}:{system_id}"
            )
            if system_run.system_run_id != expected_run_id:
                raise ValueError("system run ID does not match its frozen schedule position")
            if (
                system_run.status != "ok"
                or system_run.metrics is None
                or not system_run.same_input_verified
                or system_run.input_manifest != frozen_case.input_manifest
                or system_run.safe_provider_config_sha256 != recorder.safe_provider_config_sha256
            ):
                raise ValueError("completed result contains an unverified system run")
            for call_id in system_run.logical_call_ids:
                call = recorder.calls.get(call_id)
                if call is None or call.system_run_id != system_run.system_run_id:
                    raise ValueError("system run references a missing or foreign provider call")
                referenced_call_ids.add(call_id)
    if referenced_call_ids != recorded_call_ids:
        raise ValueError("provider recorder contains unreferenced or missing logical calls")

    logical_status_counts = Counter(call.status for call in recorder.calls.values())
    transport_status_counts = Counter(attempt.status for attempt in recorder.transport_attempts)
    logical_calls = [
        {
            "logical_call_id": call.logical_call_id,
            "system_run_id": call.system_run_id,
            "template_id": call.template_id,
            "template_version": call.template_version,
            "response_schema_name": call.response_schema_name,
            "status": call.status,
            "transport_attempt_ids": call.transport_attempt_ids,
            "error": call.error.model_dump(mode="json") if call.error else None,
        }
        for call in recorder.calls.values()
    ]
    transport_attempts = [
        {
            "attempt_id": attempt.attempt_id,
            "logical_call_id": attempt.logical_call_id,
            "status": attempt.status,
            "duration_ms": attempt.duration_ms,
            "request_sha256": attempt.request_sha256,
            "response_sha256": attempt.response_sha256,
            "error": attempt.error.model_dump(mode="json") if attempt.error else None,
        }
        for attempt in recorder.transport_attempts
    ]

    results_sha = sha256_bytes(results_bytes)
    _atomic_write(destination_path, results_bytes)
    manifest: dict[str, Any] = {
        "schema_version": "threadline-reverie-live-evaluation-publication/1.0.0",
        "artifact_id": artifact.artifact_id,
        "status": "complete",
        "synthetic_only": True,
        "same_input_and_config_verified": True,
        "spec": {
            "path": artifact.spec_path,
            "sha256": artifact.spec_sha256,
        },
        "results": {
            "authoritative_path": results_path.relative_to(REPOSITORY_ROOT).as_posix(),
            "submission_path": destination_path.relative_to(REPOSITORY_ROOT).as_posix(),
            "sha256": results_sha,
            "byte_identical": True,
        },
        "raw_provider_recorder": {
            "path": recorder_path.relative_to(REPOSITORY_ROOT).as_posix(),
            "sha256": recorder_sha,
            "contains_credentials": False,
            "logical_call_count": len(recorder.calls),
            "transport_attempt_count": len(recorder.transport_attempts),
            "logical_call_status_counts": dict(sorted(logical_status_counts.items())),
            "transport_attempt_status_counts": dict(sorted(transport_status_counts.items())),
            "logical_calls": logical_calls,
            "transport_attempts": transport_attempts,
        },
        "validation": {
            "strict_result_schema": "LiveEvaluationArtifact",
            "strict_recorder_schema": "ProviderRecorderCheckpoint",
            "complete_system_runs": artifact.completed_system_runs,
            "expected_system_runs": artifact.expected_system_runs,
            "failed_system_runs": artifact.failed_system_runs,
            "superseded_failed_call_count": len(superseded_failed_calls),
            "superseded_failed_call_ids": superseded_failed_calls,
        },
    }
    manifest_bytes = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True).encode(
        "utf-8"
    )
    _atomic_write(manifest_path, manifest_bytes)
    return {
        "results_sha256": results_sha,
        "recorder_sha256": recorder_sha,
        "manifest_sha256": sha256_bytes(manifest_bytes),
    }


def main() -> int:
    args = _arguments()
    published = publish(
        results_path=args.results,
        destination_path=args.destination,
        manifest_path=args.manifest,
    )
    print(f"results_sha256={published['results_sha256']}")
    print(f"recorder_sha256={published['recorder_sha256']}")
    print(f"manifest_sha256={published['manifest_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
