from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.schemas.models import MutationType
from app.trials import create_preview, get_trial_case, trial_cases


def test_trial_catalogue_has_eight_named_fixtures_and_all_mutations() -> None:
    cases = trial_cases()
    assert [case.case_id for case in cases] == [f"TRIAL-{index:03d}" for index in range(1, 9)]
    assert len(MutationType) == 15
    assert {item.value for item in MutationType} == {
        "transliteration_corruption",
        "spelling_corruption",
        "missing_surname",
        "estimated_age_shift",
        "missing_location",
        "changed_location",
        "impossible_timeline",
        "conflicting_distinctive_feature",
        "translation_detail_loss",
        "common_name_collision",
        "duplicate_submission",
        "equally_plausible_rivals",
        "prompt_injection",
        "source_reliability_noise",
        "contradictory_relative_information",
    }


def test_all_mutations_are_seeded_truth_preserving_and_reproducible() -> None:
    case = get_trial_case("TRIAL-001")
    selected = list(MutationType)
    first = create_preview(case, selected, 508, case.request.options.provider_mode)
    second = create_preview(case, selected, 508, case.request.options.provider_mode)
    assert first == second
    assert len(first.mutations) == 15
    assert all(item.ground_truth_changed is False for item in first.mutations)
    assert first.ground_truth == case.ground_truth


def test_trial_result_review_audit_and_export_survive_app_restart(tmp_path: Path) -> None:
    settings = Settings(
        database_path=str(tmp_path / "threadline.db"),
        export_directory=str(tmp_path / "exports"),
    )
    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/api/v1/trials/run",
            json={
                "case_id": "TRIAL-005",
                "mutation_types": ["prompt_injection"],
                "seed": 104,
                "provider_mode": "mock",
            },
        )
        assert response.status_code == 200
        trial = response.json()
        review = client.post(
            "/api/v1/reviews",
            json={
                "case_id": trial["case_id"],
                "candidate_id": None,
                "outcome": "request_more_information",
                "reviewer_id": "authorized-test-reviewer",
                "notes": "Need an independent source.",
            },
        )
        assert review.status_code == 200

    with TestClient(create_app(settings)) as restarted:
        assert restarted.get(f"/api/v1/trials/{trial['trial_run_id']}").status_code == 200
        assert restarted.get(f"/api/v1/results/{trial['result_id']}").status_code == 200
        audit = restarted.get(f"/api/v1/cases/{trial['case_id']}/audit")
        assert audit.status_code == 200
        assert audit.json()[-1]["event_type"] == "reviewer decision saved"
        exported = restarted.post(
            f"/api/v1/results/{trial['result_id']}/export", json={"format": "json"}
        )
        assert exported.status_code == 200
        manifest = exported.json()
        assert manifest["contains_credentials"] is False
        assert "LLM_API_KEY" not in manifest["content"]
        assert (tmp_path / "exports" / manifest["filename"]).exists()
