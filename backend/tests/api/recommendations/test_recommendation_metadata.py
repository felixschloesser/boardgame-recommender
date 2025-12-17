from __future__ import annotations

from datetime import datetime, timezone

from boardgames_api.domain.games.bgg_metadata import BggMetadata
from boardgames_api.domain.games.records import BoardgameRecord
from boardgames_api.domain.participants.records import StudyGroup
from boardgames_api.domain.recommendations.models import (
    RecommendationResult,
    RecommendationSelection,
)
from boardgames_api.domain.recommendations.schemas import (
    RecommendationExplanation,
    ReferenceExplanation,
)
from fastapi.testclient import TestClient

from boardgames_api.domain.recommendations import service as recommendation_service


def _make_boardgame(game_id: int) -> BoardgameRecord:
    return BoardgameRecord(
        id=game_id,
        title=f"Game {game_id}",
        description="stemmed placeholder",
        mechanics=[],
        genre=[],
        themes=[],
        min_players=1,
        max_players=4,
        complexity=1.0,
        age_recommendation=8,
        num_user_ratings=0,
        avg_user_rating=0.0,
        year_published=2020,
        playing_time_minutes=30,
        image_url="http://example.com/placeholder.jpg",
        bgg_url="http://example.com",
    )


def _create_participant_and_session(client: TestClient) -> dict:
    p_resp = client.post("/api/auth/participant", json={})
    assert p_resp.status_code == 201
    participant_id = p_resp.json().get("participant_id")
    s_resp = client.post("/api/auth/session", json={"participant_id": participant_id})
    assert s_resp.status_code == 200
    return {"participant_id": participant_id, "cookies": s_resp.cookies}


def test_recommendations_include_enriched_metadata(client: TestClient, monkeypatch):
    enriched = BggMetadata(
        description="BGG full description",
        image_url="http://images.example/full.jpg",
        fetched_at=datetime.now(timezone.utc),
    )
    from boardgames_api.domain.recommendations import repository as rec_repo

    monkeypatch.setattr(
        rec_repo.BggMetadataFetcher,
        "get",
        lambda self, bgg_id, **_: enriched,
    )

    ctx = _create_participant_and_session(client)

    def _fake_generate(
        request,
        participant_id,
        participant_repo,
        recommendation_repo,
        boardgame_repo,
        recommender=None,
        study_group_override=None,
    ):
        bg = _make_boardgame(30549)
        explanation = RecommendationExplanation(
            type="references",
            references=[ReferenceExplanation(bgg_id=13, title="Catan", influence="positive")],
            features=None,
        )
        result = RecommendationResult(
            id="rec-test",
            participant_id=participant_id,
            created_at=datetime.now(timezone.utc),
            intent=request,
            model_version="vtest",
            experiment_group=StudyGroup.REFERENCES,
            selections=[RecommendationSelection(boardgame=bg, explanation=explanation)],
        )
        recommendation_repo.save(result)
        return result

    monkeypatch.setattr(recommendation_service, "generate_recommendations", _fake_generate)

    payload = {"liked_games": [13], "play_context": {"players": 4}, "num_results": 1}
    resp = client.post("/api/recommendation", json=payload, cookies=ctx["cookies"])
    assert resp.status_code == 201
    rec_id = resp.json().get("id")

    fetched = client.get(f"/api/recommendation/{rec_id}", cookies=ctx["cookies"])
    assert fetched.status_code == 200
    rec = fetched.json()
    boardgame = rec["recommendations"][0]["boardgame"]
    assert boardgame["description"] == enriched.description
    assert boardgame["image_url"] == enriched.image_url
