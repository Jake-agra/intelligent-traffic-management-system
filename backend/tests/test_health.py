from fastapi.testclient import TestClient

from app.api.routes import health
from app.main import app


def test_health_endpoint_returns_service_and_database_status(
    monkeypatch,
) -> None:
    monkeypatch.setattr(health, "get_database_status", lambda: "ok")

    client = TestClient(app)
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "service_name": "Intelligent Traffic Management System API",
        "api_version": "0.1.0",
        "environment": "development",
        "api_status": "ok",
        "database_status": "ok",
    }
