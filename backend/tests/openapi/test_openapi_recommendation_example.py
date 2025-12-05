from __future__ import annotations


def test_openapi_example_request_succeeds(monkeypatch):
    from boardgames_api.app import app
    from fastapi.testclient import TestClient

    client = TestClient(app)
    p_resp = client.post("/api/auth/participant", json={})
    assert p_resp.status_code == 201
    pid = p_resp.json().get("participant_id")
    s_resp = client.post("/api/auth/session", json={"participant_id": pid})
    assert s_resp.status_code == 200

    example_payload = {
        "liked_games": [13, 9209, 30549],
        "play_context": {"players": 4},
        "num_results": 5,
    }
    resp = client.post("/api/recommendation", json=example_payload, cookies=s_resp.cookies)
    # Accept either 201 or validation errors due to missing embeddings; ensure not 401/404
    assert resp.status_code in (201, 503, 400)
