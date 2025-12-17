from __future__ import annotations

import importlib
from datetime import datetime, timezone

from boardgames_api.domain.games.schemas import BoardGameResponse
from boardgames_api.domain.participants.records import StudyGroup
from boardgames_api.domain.recommendations.models import RecommendationResult

from boardgames_api.domain.recommendations import routes as rec_routes
from boardgames_api.domain.recommendations import service as recommendation_service

from ...utils import assert_problem_details


def _create_participant_and_session(client) -> dict:
    p_resp = client.post("/api/auth/participant", json={})
    assert p_resp.status_code == 201
    pid = p_resp.json().get("participant_id")
    s_resp = client.post("/api/auth/session", json={"participant_id": pid})
    assert s_resp.status_code == 200
    return {
        "participant_id": pid,
        "cookies": s_resp.cookies,
        "set_cookie": s_resp.headers.get("set-cookie", ""),
    }


def _fake_store():
    class _Store:
        run_identifier = "test-run"

        def has_id(self, bgg_id: int) -> bool:
            return True

        def score_candidates(self, liked_ids, candidate_ids):  # type: ignore[no-untyped-def]
            return {int(cid): 1.0 for cid in candidate_ids}

        def get_name(self, bgg_id: int) -> str:
            return f"Game {bgg_id}"

    return _Store()


def _fake_game(game_id: int) -> BoardGameResponse:
    return BoardGameResponse(
        id=game_id,
        title=f"Game {game_id}",
        description="desc",
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
        image_url="http://example.com",
        bgg_url="http://example.com",
    )


def test_session_sets_cookie_and_allows_recommendation(client, monkeypatch):
    ctx = _create_participant_and_session(client)
    assert "session_id=" in ctx["set_cookie"]

    # Happy-path recommendation
    class _FakeRecommender:
        def recommend(self, liked_games, num_results):
            return []

    def _fake_generate(
        request,
        participant_id,
        participant_repo,
        recommendation_repo,
        boardgame_repo,
        recommender=_FakeRecommender(),
        study_group_override=None,
    ):
        result = RecommendationResult(
            id="rec-1",
            participant_id=participant_id,
            created_at=datetime.now(timezone.utc),
            intent=request,
            model_version="v1",
            experiment_group=StudyGroup.REFERENCES,
            selections=[],
        )
        recommendation_repo.save(result)
        return result

    monkeypatch.setattr(recommendation_service, "generate_recommendations", _fake_generate)

    payload = {"liked_games": [1], "play_context": {"players": 2}, "num_results": 1}
    resp = client.post("/api/recommendation", json=payload, cookies=ctx["cookies"])
    assert resp.status_code == 201
    rec_id = resp.json().get("id")

    # Auth required for retrieval
    client.cookies.clear()
    unauth = client.get(f"/api/recommendation/{rec_id}")
    assert_problem_details(unauth.json(), status=401)

    auth = client.get(f"/api/recommendation/{rec_id}", cookies=ctx["cookies"])
    assert auth.status_code == 200


def test_recommendation_validation_rejects_bad_liked_ids(client, monkeypatch):
    ctx = _create_participant_and_session(client)
    payload = {"liked_games": [0, 0], "play_context": {"players": 2}, "num_results": 1}
    resp = client.post("/api/recommendation", json=payload, cookies=ctx["cookies"])
    assert_problem_details(resp.json(), status=400)


def test_recommendation_returns_503_when_embeddings_missing(client, monkeypatch):
    ctx = _create_participant_and_session(client)

    class _FakeRecommender:
        def recommend(self, liked_games, num_results):
            raise recommendation_service.RecommendationUnavailableError(
                "Embedding index unavailable"
            )

    monkeypatch.setattr(
        recommendation_service,
        "generate_recommendations",
        lambda request,
        participant_id,
        participant_repo,
        recommendation_repo,
        boardgame_repo,
        recommender=_FakeRecommender(),
        study_group_override=None: (_ for _ in ()).throw(
            recommendation_service.RecommendationUnavailableError("Embedding index unavailable")
        ),
    )
    payload = {"liked_games": [1], "play_context": {"players": 2}, "num_results": 1}
    resp = client.post("/api/recommendation", json=payload, cookies=ctx["cookies"])
    assert_problem_details(resp.json(), status=503)


def test_recommendation_override_env_sets_study_group(monkeypatch):
    # Set override and reload routes to pick up the env.
    monkeypatch.setenv("RECOMMENDATION_OVERRIDE", "features")
    reloaded = importlib.reload(rec_routes)
    assert reloaded.OVERRIDE_STUDY_GROUP == StudyGroup.FEATURES

    # Clean up: remove override and reload to default state for other tests.
    monkeypatch.delenv("RECOMMENDATION_OVERRIDE", raising=False)
    importlib.reload(rec_routes)
