from fastapi.testclient import TestClient

import search_engine.api.main as api_main


client = TestClient(api_main.app)


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


def test_missing_index_returns_503(monkeypatch, tmp_path):
    missing_index = tmp_path / "missing-index"
    monkeypatch.setattr(api_main, "DEFAULT_INDEX_PATH", str(missing_index))

    response = client.get("/search?q=machine")

    assert response.status_code == 503
    detail = response.json()["detail"]
    assert "run indexing first" in detail["message"]
    assert "python index.py --input ANALYST" in detail["command"]


def test_invalid_ranking_model_returns_422():
    response = client.get("/search?q=machine&ranking=invalid")

    assert response.status_code == 422
