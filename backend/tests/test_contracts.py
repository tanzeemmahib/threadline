from fastapi.testclient import TestClient

from app.schemas.models import AnalyzeRequest


def test_health_and_cors(client: TestClient) -> None:
    for origin in ("http://localhost:3000", "http://127.0.0.1:3000"):
        response = client.get("/health", headers={"Origin": origin})
        assert response.status_code == 200
        assert response.json()["credentials_configured"] is False
        assert response.headers["access-control-allow-origin"] == origin


def test_analyze_frontend_and_trace_shapes(client: TestClient, demo: AnalyzeRequest) -> None:
    demo.records = demo.records[:3]
    response = client.post("/api/v1/analyze", json=demo.model_dump(mode="json"))
    assert response.status_code == 200, response.text
    body = response.json()
    assert {
        "case_id",
        "workflow_run_id",
        "status",
        "summary",
        "records",
        "candidates",
        "workflow_trace",
    } <= body.keys()
    assert len(body["workflow_trace"]) == 12
    assert {
        "node_id",
        "node_version",
        "structured_input",
        "structured_output",
        "validation_results",
    } <= body["workflow_trace_details"][0].keys()
    assert "match_probability" not in response.text.lower()


def test_error_shape(client: TestClient) -> None:
    response = client.post("/api/v1/analyze", json={"incident": {}, "records": []})
    assert response.status_code == 422
    assert {
        "request_id",
        "error_code",
        "message",
        "retryable",
        "failed_stage",
        "preserved_data",
        "details",
    } <= response.json()["error"].keys()


def test_demo_contract(client: TestClient) -> None:
    response = client.get("/api/v1/demo")
    assert response.status_code == 200
    assert response.json()["incident"]["incident_id"] == "INCIDENT-NDE-001"
