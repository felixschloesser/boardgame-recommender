from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import polars as pl
from sqlalchemy import create_engine, delete, func, inspect, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session

DATA_ROOT = Path(__file__).resolve().parents[4] / "data"
DEFAULT_DB_PATH = Path(
    os.getenv("BOARDGAMES_DB_PATH", DATA_ROOT / "app.sqlite3")
).resolve()
DEFAULT_PARQUET_PATH = Path(
    os.getenv(
        "BOARDGAMES_PARQUET_PATH",
        DATA_ROOT / "processed" / "boardgames.parquet",
    )
).resolve()


class Base(DeclarativeBase):
    """
    SQLAlchemy declarative base for ORM models.
    """

    pass


_engine: Engine | None = None


def _create_engine(db_path: Path = DEFAULT_DB_PATH) -> Engine:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(f"sqlite:///{db_path}", future=True)


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = _create_engine()
    return _engine


@contextmanager
def get_session() -> Iterator[Session]:
    engine = get_engine()
    session = Session(engine)
    try:
        yield session
    finally:
        session.close()


def init_db() -> None:
    """
    Ensure metadata is created. Call once at startup.
    """
    engine = get_engine()
    inspector = inspect(engine)

    if "recommendations" in inspector.get_table_names():
        columns = {col["name"] for col in inspector.get_columns("recommendations")}
        expected = {
            "id",
            "participant_id",
            "created_at",
            "model_version",
            "experiment_group",
            "intent",
            "recommendations",
        }
        if not expected.issubset(columns):
            # Drop legacy table schema (e.g., payload-only) to allow recreate.
            from boardgames_api.domain.recommendations.models import RecommendationRecord
            RecommendationRecord.__table__.drop(engine, checkfirst=True)  # type: ignore[attr-defined]

    # Import models here so metadata is populated without creating circular imports.
    from boardgames_api.domain.games import models as games_models  # noqa: F401
    from boardgames_api.domain.recommendations import models as rec_models  # noqa: F401
    Base.metadata.create_all(engine)


def seed_boardgames_from_parquet(
    parquet_path: Path = DEFAULT_PARQUET_PATH, db_engine: Engine | None = None
) -> int:
    """
    Load boardgame metadata from the processed parquet file into SQLite.
    Existing rows are replaced.
    """
    db_engine = db_engine or get_engine()
    if not parquet_path.exists():
        # Dataset not present in test environments; skip seeding and allow fallbacks.
        return 0

    init_db()
    df = pl.read_parquet(parquet_path)
    from boardgames_api.persistence.seeders.boardgames import row_to_record

    records = []
    for row in df.to_dicts():
        try:
            records.append(row_to_record(row))
        except Exception:
            continue

    with Session(db_engine) as session:
        from boardgames_api.domain.games.models import BoardgameRecord

        session.execute(delete(BoardgameRecord))
        session.add_all(records)
        session.commit()

    return len(records)


def ensure_seeded() -> None:
    """
    Seed the SQLite database on first use to back API lookups with realistic data.
    """
    init_db()
    engine = get_engine()
    with Session(engine) as session:
        from boardgames_api.domain.games.models import BoardgameRecord

        count = session.scalar(select(func.count(BoardgameRecord.id)))
        if count and count > 0 and not _boardgames_invalid(session):
            return
    seed_boardgames_from_parquet()


def _boardgames_invalid(session: Session) -> bool:
    """
    Detect obviously invalid data that would violate response schema constraints.
    """
    from boardgames_api.domain.games.models import BoardgameRecord

    min_complexity = session.scalar(select(func.min(BoardgameRecord.complexity)))
    min_age = session.scalar(select(func.min(BoardgameRecord.age_recommendation)))
    min_playtime = session.scalar(select(func.min(BoardgameRecord.playing_time_minutes)))
    min_min_players = session.scalar(select(func.min(BoardgameRecord.min_players)))
    placeholder_count = session.scalar(
        select(func.count()).where(
            BoardgameRecord.title == "Valid Game", BoardgameRecord.description == "Good"
        )
    ) or 0
    return any(
        value is not None and value < 0
        for value in (
            min_complexity,
            min_age,
        )
    ) or any(
        value is not None and value < 1
        for value in (
            min_playtime,
            min_min_players,
        )
    ) or placeholder_count > 0
