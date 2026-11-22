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


def test_upload_api_queues_without_inline_indexing(client: TestClient) -> None:
    response = client.post(
        "/api/v1/documents",
        files={"file": ("queued-policy.md", b"# queued\n\ncontent", "text/markdown")},
    )
    assert response.status_code == 202
    payload = response.json()
    assert payload["document"]["status"] == "queued"
    assert payload["document"]["index_task_id"] == payload["task"]["id"]
    assert payload["task"]["status"] == "queued"
    assert payload["document"]["chunk_count"] == 0

    task = client.get(f"/api/v1/indexing/tasks/{payload['task']['id']}")
    assert task.status_code == 200
    assert task.json()["status"] == "queued"

    cancelled = client.post(f"/api/v1/indexing/tasks/{payload['task']['id']}/cancel")
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"


def test_reindex_api_is_idempotent(client: TestClient) -> None:
    first = client.post("/api/v1/documents/individual-registration/reindex")
    second = client.post("/api/v1/documents/individual-registration/reindex")
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]


def test_document_detail_api(client: TestClient) -> None:
    documents = client.get("/api/v1/documents").json()
    document = documents[0]
    response = client.get(f"/api/v1/documents/{document['id']}")
    assert response.status_code == 200
    assert response.json()["id"] == document["id"]


def test_evaluation_api_persists_snapshot(client: TestClient) -> None:
    response = client.get("/api/v1/evaluations/summary")
    assert response.status_code == 200
    evaluation = response.json()
    assert evaluation["id"].startswith("eval_")

    overview = client.get("/api/v1/overview").json()
    assert overview["last_evaluation"]["id"] == evaluation["id"]


def test_overview_api(client: TestClient) -> None:
    response = client.get("/api/v1/overview")
    assert response.status_code == 200
    payload = response.json()
    assert payload["document_count"] >= 3
    assert len(payload["last_evaluation"]["rows"]) == 4
