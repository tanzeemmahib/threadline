from fastapi.testclient import TestClient

from app.schemas.models import AnalyzeRequest

SMALL_CONFIG = {
    "seed": 44,
    "identities": 3,
    "records_per_identity": 2,
    "languages": ["English", "Arabic", "French"],
}


def test_complete_baseline_comparison(client: TestClient, demo: AnalyzeRequest) -> None:
    demo.records = demo.records[:2]
    response = client.post("/api/v1/baselines/run", json={"case": demo.model_dump(mode="json")})
    assert response.status_code == 200, response.text
    assert [item["system_id"] for item in response.json()["systems"]] == [
        "fuzzy",
        "generic",
        "structured",
        "threadline",
    ]


def test_deterministic_benchmark_generation_and_execution(client: TestClient) -> None:
    generated = client.post("/api/v1/benchmark/generate", json={"configuration": SMALL_CONFIG})
    assert generated.status_code == 200, generated.text
    dataset = generated.json()
    repeated = client.post(
        "/api/v1/benchmark/generate", json={"configuration": SMALL_CONFIG}
    ).json()
    assert dataset["content_hash"] == repeated["content_hash"]
    executed = client.post(
        "/api/v1/benchmark/run",
        json={"dataset": dataset, "provider_mode": "mock", "candidate_k": 5},
    )
    assert executed.status_code == 200, executed.text
    assert len(executed.json()["systems"]) == 4
    assert all(system["metrics"] for system in executed.json()["systems"])


def test_ablation_execution(client: TestClient) -> None:
    response = client.post(
        "/api/v1/ablation/run",
        json={
            "configuration": SMALL_CONFIG,
            "disabled_nodes": ["normalization"],
            "provider_mode": "mock",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert [item["configuration_id"] for item in body["configurations"]] == [
        "full",
        "no-normalization",
    ]
    assert body["evaluation_mode"] == "Deterministic mock evaluation"


def test_invalid_ablation_configuration(client: TestClient) -> None:
    response = client.post(
        "/api/v1/ablation/run",
        json={"configuration": SMALL_CONFIG, "disabled_nodes": ["review"], "provider_mode": "mock"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["error_code"] == "BENCHMARK_CONFIGURATION_INVALID"
