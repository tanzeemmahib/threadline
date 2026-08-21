from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from app.api.routes import reverie as reverie_routes
from app.main import create_app
from app.services.identity_benchmark import RECORD_EXPECTED_FIELDS


def _artifact() -> dict[str, Any]:
    repository_root = Path(__file__).resolve().parents[2]
    path = repository_root / "docs" / "submission" / "reverie-prompt-lab.json"
    return json.loads(path.read_text("utf-8"))


def _case(kind: str) -> dict[str, Any]:
    return next(case for case in _artifact()["cases"] if case["kind"] == kind)


def test_prompt_lab_endpoint_is_read_only_locked_artifact(settings: Any) -> None:
    client = TestClient(create_app(settings))
    response = client.get("/api/v1/reverie/prompt-lab")
    assert response.status_code == 200
    assert response.json() == _artifact()


def test_prompt_lab_endpoint_fails_closed_for_malformed_artifact(
    settings: Any, monkeypatch: Any
) -> None:
    def malformed() -> dict[str, Any]:
        return {"schema_version": "unsupported"}

    monkeypatch.setattr(reverie_routes, "_prompt_lab_artifact", malformed)
    client = TestClient(create_app(settings))
    response = client.get("/api/v1/reverie/prompt-lab")
    assert response.status_code == 503
    assert response.json()["detail"] == {
        "error_code": "REVERIE_ARTIFACT_UNAVAILABLE",
        "message": "The locked synthetic Prompt Lab artifact is unavailable or malformed.",
        "retryable": True,
    }


def test_prompt_lab_endpoint_fails_closed_on_nested_span_and_provenance_drift(
    settings: Any, monkeypatch: Any
) -> None:
    client = TestClient(create_app(settings))
    source_span_drift = deepcopy(_artifact())
    source_span_drift["cases"][0]["source_spans"][0]["quote"] = "x" * len(
        source_span_drift["cases"][0]["source_spans"][0]["quote"]
    )
    monkeypatch.setattr(reverie_routes, "_prompt_lab_artifact", lambda: source_span_drift)
    response = client.get("/api/v1/reverie/prompt-lab")
    assert response.status_code == 503

    provenance_drift = deepcopy(_artifact())
    provenance_drift["winning_story"]["provenance"]["replay_manifest"][
        "audit_chain_terminal_hash"
    ] = "0" * 64
    monkeypatch.setattr(reverie_routes, "_prompt_lab_artifact", lambda: provenance_drift)
    response = client.get("/api/v1/reverie/prompt-lab")
    assert response.status_code == 503


def test_one_shot_and_workflow_use_identical_inputs() -> None:
    for case in _artifact()["cases"]:
        manifest = case["input_manifest"]
        assert case["identical_input_verified"] is True
        for system in case["systems"].values():
            assert system["candidate_record_ids"] == manifest["record_ids"]
        canonical = json.dumps(
            [
                {"record_id": record["record_id"], "text": record["text"]}
                for record in case["records"]
            ],
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        assert hashlib.sha256(canonical).hexdigest() == manifest["input_sha256"]


def test_source_spans_resolve_to_exact_original_text() -> None:
    for case in _artifact()["cases"]:
        records = {record["record_id"]: record["text"] for record in case["records"]}
        for span in case["source_spans"]:
            assert records[span["record_id"]][span["start"] : span["end"]] == span["quote"]


def test_archived_live_fields_identify_supported_and_unsupported_keys() -> None:
    for case in _artifact()["cases"]:
        for record in case["records"]:
            live = record["archived_live_v2_extraction"]
            extracted = {field["key"] for field in live["fields"]}
            expected = RECORD_EXPECTED_FIELDS[record["record_id"]]
            assert set(live["supported_field_keys"]) == extracted & expected
            assert set(live["unsupported_field_keys"]) == extracted - expected
            assert set(live["missed_field_keys"]) == expected - extracted


def test_blocking_dob_conflict_cannot_be_overridden() -> None:
    case = _case("blocking_identity_conflict")
    assert case["systems"]["one_shot"]["classification"] == "possible_candidate"
    assert case["decision"]["state"] == "blocked_by_conflict"
    assert case["decision"]["release_allowed_for_authorized_review"] is False
    assert "date_of_birth_conflict" in case["decision"]["reason_codes"]
    assert case["decision"]["blocking_conflicts"][0]["reason_code"] == "dob_year_mismatch"


def test_cross_script_case_preserves_native_text_and_requires_review() -> None:
    case = _case("cross_script_partial")
    assert any(record["language"] == "Arabic" for record in case["records"])
    assert any("يوسف" in record["text"] for record in case["records"])
    assert case["decision"]["state"] == "human_review_required"
    assert case["decision"]["state"] != "link_recommended"


def test_shared_contact_never_becomes_autonomous_link() -> None:
    case = _case("shared_contact_insufficient")
    assert case["ground_truth"]["relation"] == "different_identity"
    assert case["decision"]["state"] in {"human_review_required", "insufficient_evidence"}
    assert case["decision"]["state"] != "link_recommended"


def test_prompt_versions_and_metrics_match_locked_sources() -> None:
    artifact = _artifact()
    repository_root = Path(__file__).resolve().parents[2]
    prompts = artifact["prompt_iterations"]["prompts"]
    for version, prompt in prompts.items():
        path = repository_root / prompt["source_path"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == prompt["sha256"]
        assert prompt["version"] == version

    for cohort in artifact["prompt_iterations"]["cohorts"]:
        for run in cohort["runs"]:
            live_path = next(
                repository_root / path
                for path in run["source_files"]
                if path.endswith("live-artifact.json")
            )
            live = json.loads(live_path.read_text("utf-8"))
            assert run["prompt_version"] == live["prompt_version"]
            assert run["extraction_quality"] == live["extraction_quality"]
            assert run["decision_metrics"] == live["metrics"]

    decision = artifact["prompt_iterations"]["promotion_decision"]
    assert decision["production_version"] == "v2"
    assert decision["not_promoted"] == "v3"
    assert decision["v3_precision"] < decision["v2_precision"]
    assert decision["v3_f1"] < decision["v2_f1"]


def test_winning_story_contains_supported_pair_and_blocked_rival() -> None:
    story = _artifact()["winning_story"]
    by_pair = {frozenset(candidate["record_ids"]): candidate for candidate in story["candidates"]}
    supported = by_pair[frozenset(story["supported_pair"])]
    rival = by_pair[frozenset(story["blocked_rival_pair"])]
    assert supported["linkage_decision"]["state"] == "link_recommended"
    assert rival["linkage_decision"]["state"] == "blocked_by_conflict"
    contracts = {contract["candidate_id"]: contract for contract in story["evidence_contracts"]}
    assert contracts[supported["candidate_id"]]["release_allowed_for_authorized_review"] is True
    assert contracts[rival["candidate_id"]]["release_allowed_for_authorized_review"] is False
    provenance = story["provenance"]
    assert provenance["workflow_run_id"].startswith("RUN-MOCK-")
    assert provenance["audit_integrity"]["valid"] is True
    assert len(provenance["audit_integrity"]["terminal_hash"]) == 64
    assert (
        provenance["audit_integrity"]["terminal_hash"]
        == provenance["replay_manifest"]["audit_chain_terminal_hash"]
    )
    assert provenance["replay_certificate"] == "Not recorded"
    assert provenance["export_artifact"] == "Not recorded"
