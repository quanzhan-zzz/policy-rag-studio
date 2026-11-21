from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health() -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_compare_api() -> None:
    response = client.post(
        "/api/v1/retrieval/compare",
        json={
            "query": "青年人才租房补贴申报条件",
            "strategies": ["dense", "bm25", "hybrid", "hybrid_rerank"],
            "chunk_strategy": "heading",
            "top_k": 5,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["runs"]) == 4
    assert payload["runs"][-1]["results"]


def test_overview_api() -> None:
    response = client.get("/api/v1/overview")
    assert response.status_code == 200
    payload = response.json()
    assert payload["document_count"] >= 3
    assert len(payload["last_evaluation"]["rows"]) == 4
