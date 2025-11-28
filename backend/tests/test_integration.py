from boardgames_api.app import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_list_boardgames() -> None:
    """
    Integration test for the /api/games/ endpoint.
    Ensures the API responds with a 200 status and returns a paginated list of board games.
    """
    response = client.get("/api/games/")
    assert response.status_code == 200
    assert "items" in response.json()
    assert "total" in response.json()


def test_retrieve_boardgame() -> None:
    """
    Integration test for the /api/games/{bgg_id} endpoint.
    Ensures the API responds with a 200 status for a valid board game ID and 404 for an invalid ID.
    """
    valid_id = 1  # Replace with a valid ID from your dataset
    invalid_id = 999999  # Replace with an ID that doesn't exist

    response = client.get(f"/api/games/{valid_id}")
    assert response.status_code == 200
    assert "bgg_url" in response.json()

    response = client.get(f"/api/games/{invalid_id}")

    assert response.status_code == 404
    assert response.json() == {"detail": "Game not found."}


def test_create_recommendations() -> None:
    """
    Integration test for the /api/recommendations/ endpoint.
    Ensures the API responds with a 201 status for valid requests and 400 for invalid requests.
    """
    valid_request = {
        "liked_games": [1, 2],
        "player_count": 3,
        "available_time_minutes": 90,
        "amount": 3,
    }
    invalid_request = {
        "liked_games": [],
        "player_count": 0,
        "available_time_minutes": -10,
        "amount": 0,
    }

    response = client.post("/api/recommendations/", json=valid_request)
    assert response.status_code == 201
    assert "recommendations" in response.json()

    response = client.post("/api/recommendations/", json=invalid_request)
    assert response.status_code == 400
    body = response.json()
    assert body.get("status") == 400
    assert body.get("title")


def test_retrieve_recommendation_session() -> None:
    """
    Integration test for the /api/recommendations/{session_id} endpoint.
    Ensures the API responds with a 200 status for a valid session ID and 404 for an invalid ID.
    """
    valid_session_id = (
        "mock_session_id"  # Use the mock session ID expected by the implementation
    )
    invalid_session_id = "invalid-session-id"  # Replace with an invalid session ID

    response = client.get(f"/api/recommendations/{valid_session_id}")
    assert response.status_code == 200
    assert "recommendations" in response.json()

    response = client.get(f"/api/recommendations/{invalid_session_id}")
    assert response.status_code == 404
    body = response.json()
    assert body.get("status") == 404
    assert body.get("title")
