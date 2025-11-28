from boardgames_api.app import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_health_check() -> None:
    """
    Integration test for the /health endpoint.
    Ensures the API responds with a 200 status and the correct JSON payload.
    """
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
