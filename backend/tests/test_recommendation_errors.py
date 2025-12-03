from __future__ import annotations

from boardgames_api.app import app
from boardgames_api.domain.games.schemas import BoardGameResponse
from boardgames_api.domain.recommendations import service as recommendation_service
from fastapi.testclient import TestClient


class _FakeStore:
    def __init__(self, run_identifier: str = "test"):
        self.run_identifier = run_identifier

    def has_id(self, bgg_id: int) -> bool:
        return True

    def get_name(self, bgg_id: int) -> str | None:
        return f"Game {bgg_id}"

    def score_candidates(self, liked_ids, candidate_ids):  # type: ignore[no-untyped-def]
        return {int(cid): float(cid) for cid in candidate_ids}


def _fake_game(game_id: int, *, min_players: int, max_players: int) -> BoardGameResponse:
    return BoardGameResponse(
        id=str(game_id),
        title=f"Game {game_id}",
        description="desc",
        mechanics=[],
        genre=[],
        themes=[],
        min_players=min_players,
        max_players=max_players,
        complexity=1.0,
        age_recommendation=8,
        num_user_ratings=0,
        avg_user_rating=0.0,
        year_published=2020,
        playing_time_minutes=30,
        image_url="http://example.com",
        bgg_url="http://example.com",
    )


def test_recommendation_returns_400_when_no_candidates(monkeypatch):
    """
    API should return 400 (not 500) when filters remove all candidates.
    """
    client = TestClient(app)
    session_resp = client.post("/api/auth/session", json={"study_token": "token"})
    assert session_resp.status_code == 200

    games = [_fake_game(1, min_players=1, max_players=4)]
    monkeypatch.setattr(recommendation_service, "_load_boardgames", lambda: games)
    monkeypatch.setattr(recommendation_service, "get_embedding_store", lambda: _FakeStore())

    payload = {
        "liked_games": [1],
        "play_context": {"players": 99, "duration": "long"},
        "num_results": 3,
    }
    resp = client.post(
        "/api/recommendation",
        json=payload,
        cookies=session_resp.cookies,
    )
    assert resp.status_code == 400
    body = resp.json()
    detail = body.get("detail") if isinstance(body, dict) else ""
    assert "No recommendations" in str(detail)
