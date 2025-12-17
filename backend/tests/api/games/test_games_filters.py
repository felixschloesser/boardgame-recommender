from __future__ import annotations


def test_games_filters_are_case_insensitive_prefix(client) -> None:
    """
    Query filters for genre/mechanics/themes should be case-insensitive and prefix-based.
    """
    resp = client.get("/api/games/", params={"genre": "Strat"})
    assert resp.status_code == 200
    items = resp.json().get("items", [])
    assert isinstance(items, list)
    # Genres should include at least one value starting with "strat" (case-insensitive).
    assert items, "expected at least one game for prefix 'Strat'"
    for item in items:
        genres = [g.lower() for g in item.get("genre", [])]
        assert any(g.startswith("strat") for g in genres)
