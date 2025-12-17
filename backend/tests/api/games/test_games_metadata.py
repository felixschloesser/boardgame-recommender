from __future__ import annotations

from datetime import datetime, timezone

from boardgames_api.domain.games import bgg_metadata
from fastapi.testclient import TestClient


def test_game_detail_returns_enriched_description_and_image(client: TestClient, monkeypatch):
    """
    The game detail endpoint should surface the richer BGG description/image when available.
    """
    enriched = bgg_metadata.BggMetadata(
        description="Full BGG description for testing.",
        image_url="http://images.example/full.jpg",
        fetched_at=datetime.now(timezone.utc),
    )
    monkeypatch.setattr(
        bgg_metadata.BggMetadataFetcher,
        "get",
        lambda self, bgg_id, allow_live_fetch=True: enriched,
    )

    list_resp = client.get("/api/games/", params={"limit": 1})
    assert list_resp.status_code == 200
    items = list_resp.json().get("items") or []
    assert items, "expected at least one game from seed data"
    first_id = items[0]["id"]

    resp = client.get(f"/api/games/{first_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["description"] == enriched.description
    assert data["image_url"] == enriched.image_url
