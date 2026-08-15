from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from app.schemas.models import AuditActorType
from app.services.audit_chain import append_audit_event, verify_audit_chain


def _analyze_v1(client: TestClient, scenario: str) -> dict[str, object]:
    demo = client.get(f"/api/v1/demo/v1/{scenario}")
    assert demo.status_code == 200, demo.text
    response = client.post("/api/v1/analyze", json=demo.json())
    assert response.status_code == 200, response.text
    return response.json()


def test_v1_proof_routes_are_wired_end_to_end(client: TestClient) -> None:
    body = _analyze_v1(client, "passing")
    run_id = str(body["workflow_run_id"])
    candidate = body["candidates"][0]
    contract = body["evidence_contract"]

    assert body["contract_release_status"] == "released"
    assert contract["release_allowed"] is True
    assert contract["contract_status"] == "passed_with_review_requirements"
    assert body["release_state"]["state"] == "authorized_review_required"

    stored = client.get(f"/api/v1/contracts/{contract['contract_id']}")
    assert stored.status_code == 200, stored.text
    assert stored.json()["candidate_id"] == candidate["candidate_id"]

    integrity = client.get(f"/api/v1/runs/{run_id}/audit/verify")
    assert integrity.status_code == 200, integrity.text
    assert integrity.json()["status"] == "verified"
    assert integrity.json()["valid"] is True

    replay = client.post(f"/api/v1/runs/{run_id}/replay")
    assert replay.status_code == 200, replay.text
    assert replay.json()["replay_status"] == "exact_match"

    unknown_candidate = client.post(
        f"/api/v1/runs/{run_id}/counterfactuals",
        json={
            "candidate_id": "CANDIDATE-NOT-IN-RUN",
            "counterfactual_type": "remove_source_record",
            "source_record_id": candidate["record_a_id"],
        },
    )
    assert unknown_candidate.status_code == 422

    wrong_source = client.post(
        f"/api/v1/runs/{run_id}/counterfactuals",
        json={
            "candidate_id": candidate["candidate_id"],
            "counterfactual_type": "remove_source_record",
            "source_record_id": "RECORD-NOT-IN-CANDIDATE",
        },
    )
    assert wrong_source.status_code == 422

    counterfactual = client.post(
        f"/api/v1/runs/{run_id}/counterfactuals",
        json={
            "candidate_id": candidate["candidate_id"],
            "counterfactual_type": "remove_source_record",
            "source_record_id": candidate["record_a_id"],
        },
    )
    assert counterfactual.status_code == 200, counterfactual.text
    assert counterfactual.json()["decision_changed"] is True


def test_frontend_review_payload_records_chained_release_state(client: TestClient) -> None:
    body = _analyze_v1(client, "passing")
    run_id = str(body["workflow_run_id"])
    candidate = body["candidates"][0]
    contract = body["evidence_contract"]
    response = client.post(
        "/api/v1/reviews",
        json={
            "case_id": body["case_id"],
            "candidate_id": candidate["candidate_id"],
            "outcome": "additional_evidence_required",
            "reviewer_id": "authorized-case-reviewer",
            "notes": "Independent transport record is still required.",
            "rationale": "The missing interval remains material.",
            "remaining_uncertainty": ["Movement between records is unverified."],
            "requested_evidence": ["Independent transport record"],
            "workflow_run_id": run_id,
            "contract_id": contract["contract_id"],
            "referenced_artifact_ids": [candidate["candidate_id"]],
        },
    )
    assert response.status_code == 200, response.text
    receipt = response.json()
    assert receipt["candidate_id"] == candidate["candidate_id"]
    assert receipt["audit_chain_event_id"]
    assert receipt["release_state"]["state"] == "authorized_review_in_progress"

    integrity = client.get(f"/api/v1/runs/{run_id}/audit/verify")
    assert integrity.status_code == 200, integrity.text
    assert integrity.json()["valid"] is True


def test_blocked_release_view_withholds_decision_fields(client: TestClient) -> None:
    body = _analyze_v1(client, "blocked")
    candidate = body["candidates"][0]
    material_violation = next(
        item
        for item in body["evidence_contract"]["violations"]
        if item["rule_id"] == "EC-007"
    )
    assert body["contract_release_status"] == "withheld"
    assert body["evidence_contract"]["release_allowed"] is False
    assert any("AGE" in span_id for span_id in material_violation["evidence_span_ids"])
    assert "location" not in material_violation["message"].lower()
    assert candidate["label"] == "Output withheld"
    assert candidate["classification"] is None
    assert candidate["classification_code"] is None
    assert candidate["retrieval_score"] is None
    assert candidate["rank"] is None
    assert candidate["score_components"] == []
    assert candidate["linkage_decision"] is None


def test_repeat_mock_analysis_preserves_review_chain(client: TestClient) -> None:
    demo = client.get("/api/v1/demo/v1/passing").json()
    first = client.post("/api/v1/analyze", json=demo).json()
    candidate = first["candidates"][0]
    contract = first["evidence_contract"]
    review = client.post(
        "/api/v1/reviews",
        json={
            "case_id": first["case_id"],
            "candidate_id": candidate["candidate_id"],
            "outcome": "additional_evidence_required",
            "reviewer_id": "authorized-reviewer",
            "workflow_run_id": first["workflow_run_id"],
            "contract_id": contract["contract_id"],
        },
    )
    assert review.status_code == 200, review.text
    before = client.get(
        f"/api/v1/runs/{first['workflow_run_id']}/audit"
    ).json()["events"]

    repeated = client.post("/api/v1/analyze", json=demo)
    assert repeated.status_code == 200, repeated.text
    repeated_body = repeated.json()
    assert repeated_body["workflow_run_id"] == first["workflow_run_id"]
    assert repeated_body["release_state"]["state"] == "authorized_review_in_progress"
    after = client.get(
        f"/api/v1/runs/{first['workflow_run_id']}/audit"
    ).json()["events"]
    assert len(after) == len(before)
    assert after[-1]["event_type"] == "human_review_requested"


def test_contract_export_requires_run_membership(client: TestClient) -> None:
    passing = _analyze_v1(client, "passing")
    blocked = _analyze_v1(client, "blocked")
    contract_id = passing["evidence_contract"]["contract_id"]

    missing = client.post(
        f"/api/v1/runs/RUN-NOT-FOUND/contracts/{contract_id}/export"
    )
    assert missing.status_code == 404
    mismatched = client.post(
        f"/api/v1/runs/{blocked['workflow_run_id']}/contracts/{contract_id}/export"
    )
    assert mismatched.status_code == 409


def test_audit_verifier_signs_actor_time_event_id_and_run() -> None:
    events = []
    append_audit_event(
        events,
        workflow_run_id="RUN-AUDIT-BOUND",
        event_type="test_event",
        payload={"value": 1},
        created_at=datetime(2026, 4, 18, 22, 2, tzinfo=UTC),
        actor_type=AuditActorType.system,
        actor_id="system-a",
    )
    assert verify_audit_chain("RUN-AUDIT-BOUND", events).valid is True

    actor_tampered = [events[0].model_copy(update={"actor_id": "system-b"})]
    assert verify_audit_chain("RUN-AUDIT-BOUND", actor_tampered).valid is False
    time_tampered = [
        events[0].model_copy(update={"created_at": events[0].created_at + timedelta(seconds=1)})
    ]
    assert verify_audit_chain("RUN-AUDIT-BOUND", time_tampered).valid is False
    id_tampered = [events[0].model_copy(update={"event_id": "CHAIN-TAMPERED"})]
    assert verify_audit_chain("RUN-AUDIT-BOUND", id_tampered).valid is False
    assert verify_audit_chain("RUN-OTHER", events).valid is False
