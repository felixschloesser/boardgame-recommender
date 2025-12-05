from __future__ import annotations

from boardgames_api.app import app


def test_openapi_games_get_has_no_body() -> None:
    """
    Ensure GET /api/games does not declare a requestBody (regression for swagger UI errors).
    """
    schema = app.openapi()
    games_get = schema["paths"]["/api/games/"]["get"]
    assert games_get.get("requestBody") in (None, {})
