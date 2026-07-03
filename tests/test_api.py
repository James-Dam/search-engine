from fastapi.testclient import TestClient

from search_engine.api.main import app


client = TestClient(app)


def test_health_endpoint_returns_ok():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_empty_query_returns_400():
    response = client.get("/search?q=")

    assert response.status_code == 400
    assert "must not be empty" in response.json()["detail"]["message"]


def test_blank_query_returns_400():
    response = client.get("/search?q=%20%20")

    assert response.status_code == 400
    assert "must not be empty" in response.json()["detail"]["message"]
