from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health() -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "policy-rag-studio",
        "mode": "development",
    }


def test_root_points_to_docs_and_health() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["docs"] == "/docs"
