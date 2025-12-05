from boardgames_api.domain.games.records import BoardgameRecord
from boardgames_api.persistence.database import ensure_seeded
from sqlalchemy import func, select


def test_seed_loads_and_fields_non_negative() -> None:
    """
    Integration test focused on persistence: seed data loads and respects schema bounds.
    """
    ensure_seeded()
    from boardgames_api.persistence.database import session_scope
    with session_scope() as session:
        total = session.scalar(select(func.count(BoardgameRecord.id)))
        min_complexity = session.scalar(select(func.min(BoardgameRecord.complexity)))
        min_age = session.scalar(select(func.min(BoardgameRecord.age_recommendation)))
        min_playtime = session.scalar(select(func.min(BoardgameRecord.playing_time_minutes)))
        min_min_players = session.scalar(select(func.min(BoardgameRecord.min_players)))

    assert total is not None and total > 0
    assert (min_complexity is None) or (min_complexity >= 0)
    assert (min_age is None) or (min_age >= 0)
    assert min_playtime is None or min_playtime >= 1
    assert min_min_players is None or min_min_players >= 1
