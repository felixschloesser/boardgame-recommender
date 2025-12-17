from __future__ import annotations

from boardgames_api.domain.participants.repository import ParticipantRepository
from boardgames_api.infrastructure import database


def test_participant_persists_across_client_recreation(tmp_path, monkeypatch):
    # Use isolated DB
    db_path = tmp_path / "persist.sqlite3"
    monkeypatch.setenv("BOARDGAMES_DB_PATH", str(db_path))
    monkeypatch.setattr(database, "_engine", None, raising=False)
    monkeypatch.setattr(database, "DEFAULT_DB_PATH", db_path, raising=False)
    monkeypatch.setattr(database, "SessionLocal", None, raising=False)
    database.init_db()

    from boardgames_api.app import app
    from fastapi.testclient import TestClient

    client = TestClient(app)
    p_resp = client.post("/api/auth/participant", json={})
    assert p_resp.status_code == 201
    pid = p_resp.json().get("participant_id")

    # Recreate client (simulating restart)
    client.close()
    client = TestClient(app)

    # Session should still find participant
    s_resp = client.post("/api/auth/session", json={"participant_id": pid})
    assert s_resp.status_code == 200

    # Verify repository can load participant
    with database.get_session() as session:
        repo = ParticipantRepository(session)
        participant = repo.get(pid)
        assert participant is not None
