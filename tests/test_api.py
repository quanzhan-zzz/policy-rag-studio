from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


def test_health(client: TestClient) -> None:
    response = client.get("/api/v1/health", headers={"x-request-id": "req_test"})
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["mode"] == "memory"
    assert response.json()["version"] == "0.2.0"
    assert response.headers["x-request-id"] == "req_test"


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


def test_official_document_exposes_provenance_and_chunks(client: TestClient) -> None:
    documents = client.get("/api/v1/documents").json()
    official = next(document for document in documents if document["source_url"])
    assert official["source_name"] == "江苏政务服务网·常州法人服务"
    assert official["source_retrieved_at"]
    assert len(official["source_sha256"] or "") == 64

    for strategy in ("fixed", "heading", "recursive"):
        response = client.get(
            f"/api/v1/documents/{official['id']}/chunks",
            params={"strategy": strategy},
        )
        assert response.status_code == 200
        assert response.json()


def test_evaluation_api_persists_snapshot(client: TestClient) -> None:
    response = client.get("/api/v1/evaluations/summary")
    assert response.status_code == 200
    evaluation = response.json()
    assert evaluation["id"].startswith("eval_")

    overview = client.get("/api/v1/overview").json()
    assert overview["last_evaluation"]["id"] == evaluation["id"]


def test_official_evaluation_dataset_api(client: TestClient) -> None:
    response = client.get(
        "/api/v1/evaluations/summary",
        params={"dataset": "policy-official-v1", "split": "test"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["dataset_name"] == "policy-official-v1"
    assert payload["split"] == "test"
    assert payload["case_count"] == 20
    assert len(payload["rows"]) == 4


def test_overview_api(client: TestClient) -> None:
    response = client.get("/api/v1/overview")
    assert response.status_code == 200
    payload = response.json()
    assert payload["document_count"] >= 3
    assert len(payload["last_evaluation"]["rows"]) == 4


def test_answer_stream_api(client: TestClient, monkeypatch) -> None:
    class FakeStreamingLLM:
        name = "fake-stream"

        def chat(self, messages, *, temperature=0.1, max_tokens=800):
            return "回答[1]"

        def stream_chat(self, messages, *, temperature=0.1, max_tokens=800):
            yield "回答"
            yield "[1]"

    monkeypatch.setattr("app.services.answer.get_llm_provider", lambda: FakeStreamingLLM())
    with client.stream(
        "POST",
        "/api/v1/answer/stream",
        json={
            "query": "青年人才租房补贴在哪里办理",
            "chunk_strategy": "heading",
            "top_k": 2,
        },
    ) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        body = "".join(response.iter_text())

    assert "event: meta" in body
    assert "event: delta" in body
    assert "event: done" in body
    assert "\"invalid_citation_ids\": []" in body
