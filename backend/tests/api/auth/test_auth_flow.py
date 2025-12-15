from __future__ import annotations

from boardgames_api.domain.games.schemas import BoardGameResponse

from boardgames_api.domain.recommendations import service as recommendation_service

from ...utils import assert_problem_details


def _make_participant(client) -> str:
    resp = client.post("/api/auth/participant", json={})
    assert resp.status_code == 201
    pid = resp.json().get("participant_id")
    assert isinstance(pid, str)
    return pid


def _make_session(client, participant_id: str):
    resp = client.post("/api/auth/session", json={"participant_id": participant_id})
    assert resp.status_code == 200
    return resp.cookies


def test_participant_requires_empty_object_body(client):
    resp = client.post("/api/auth/participant", data="null")
    assert resp.status_code == 400
    assert_problem_details(resp.json(), status=400)

    resp = client.post("/api/auth/participant", json={"unexpected": 1})
    assert resp.status_code == 400
    assert_problem_details(resp.json(), status=400)


def test_session_requires_existing_participant_and_prefix(client):
    # missing prefix should be rejected by validation
    resp = client.post("/api/auth/session", json={"participant_id": "123"})
    assert resp.status_code == 400 or resp.status_code == 422

    # empty body/null rejected
    resp = client.post("/api/auth/session", data="null")
    assert resp.status_code in (400, 422)

    # unknown but well-formed id returns 404
    resp = client.post("/api/auth/session", json={"participant_id": "participant-unknown"})
    assert resp.status_code == 404
    assert_problem_details(resp.json(), status=404)


def test_play_context_rejects_additional_properties(client, monkeypatch):
    participant_id = _make_participant(client)
    cookies = _make_session(client, participant_id)

    # Stub embedding store and candidates to avoid external dependencies.
    class _FakeStore:
        run_identifier = "test"

        def has_id(self, bgg_id: int) -> bool:
            return True

        def score_candidates(self, liked_ids, candidate_ids):  # type: ignore[no-untyped-def]
            return {int(cid): 1.0 for cid in candidate_ids}

        def get_name(self, bgg_id: int) -> str:
            return f"Game {bgg_id}"

    def _fake_game(game_id: int) -> BoardGameResponse:
        return BoardGameResponse(
            id=str(game_id),
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

    monkeypatch.setattr(
        recommendation_service,
        "_fetch_candidates",
        lambda play_context, desired_results, db, bgg: [_fake_game(1)],
    )
    monkeypatch.setattr(recommendation_service, "get_embedding_index", lambda: _FakeStore())

    payload = {
        "liked_games": [1],
        "play_context": {"players": 2, "duration": "short", "extra": {}},
        "num_results": 3,
    }
    resp = client.post("/api/recommendation", json=payload, cookies=cookies)
    assert resp.status_code == 400
    assert_problem_details(resp.json(), status=400)
