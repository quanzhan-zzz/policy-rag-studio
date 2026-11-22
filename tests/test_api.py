from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


def test_health(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["mode"] == "memory"


def test_compare_api(client: TestClient) -> None:
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


def test_document_detail_api(client: TestClient) -> None:
    documents = client.get("/api/v1/documents").json()
    document = documents[0]
    response = client.get(f"/api/v1/documents/{document['id']}")
    assert response.status_code == 200
    assert response.json()["id"] == document["id"]


def test_overview_api(client: TestClient) -> None:
    response = client.get("/api/v1/overview")
    assert response.status_code == 200
    payload = response.json()
    assert payload["document_count"] >= 3
    assert len(payload["last_evaluation"]["rows"]) == 4
