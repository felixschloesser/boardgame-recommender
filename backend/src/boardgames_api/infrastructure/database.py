from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import polars as pl
from sqlalchemy import create_engine, delete, func, inspect, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

DATA_ROOT = Path(__file__).resolve().parents[4] / "data"
DEFAULT_DB_PATH = Path(os.getenv("BOARDGAMES_DB_PATH", DATA_ROOT / "app.sqlite3")).resolve()
DEFAULT_PARQUET_PATH = Path(
    os.getenv(
        "BOARDGAMES_PARQUET_PATH",
        DATA_ROOT / "processed" / "boardgames.parquet",
    )
).resolve()
MIN_BOARDGAMES_COUNT = 1000

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """
    SQLAlchemy declarative base for ORM models.
    """

    pass


_engine: Engine | None = None
SessionLocal: sessionmaker | None = None


def _create_engine(db_path: Path | None = None) -> Engine:
    resolved_path = db_path or DEFAULT_DB_PATH
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        f"sqlite:///{resolved_path}",
        future=True,
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    # Reduce write contention under concurrent access. If the DB is locked at startup,
    # continue with defaults rather than failing to boot.
    try:
        with engine.connect() as conn:
            conn.exec_driver_sql("PRAGMA journal_mode=WAL")
            conn.exec_driver_sql("PRAGMA busy_timeout=30000")
    except Exception as exc:
        logger.warning("Unable to set SQLite pragmas (continuing with defaults): %s", exc)
    return engine


def get_engine() -> Engine:
    global _engine, SessionLocal
    if _engine is None:
        SessionLocal = None  # reset session factory when engine rebuilds
        _engine = _create_engine()
    return _engine


def get_session() -> Session:
    """
    Create a new SQLAlchemy session. Callers manage lifecycle (use as context manager).
    """
    engine = get_engine()
    global SessionLocal
    if SessionLocal is None:
        SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return SessionLocal()


@contextmanager
def session_scope() -> Iterator[Session]:
    """
    Context manager for a session; commits on success, rolls back on error.
    """
    session = get_session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
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
            from boardgames_api.domain.recommendations.records import (
                RecommendationRecord,
            )

            RecommendationRecord.__table__.drop(engine, checkfirst=True)  # type: ignore[attr-defined]

    # Import records so metadata is populated without circular imports.
    from boardgames_api.domain.games import records as games_records  # noqa: F401
    from boardgames_api.domain.participants import records as participants_records  # noqa: F401
    from boardgames_api.domain.recommendations import (
        records as recommendations_records,  # noqa: F401
    )

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
    from boardgames_api.infrastructure.seeders.boardgames import row_to_record

    records = []
    skipped = 0
    for row in df.to_dicts():
        try:
            records.append(row_to_record(row))
        except Exception:
            skipped += 1
            continue

    with Session(db_engine) as session:
        from boardgames_api.domain.games.records import BoardgameRecord

        session.execute(delete(BoardgameRecord))
        session.add_all(records)
        session.commit()

    if not records:
        raise RuntimeError("No valid boardgame records were loaded from parquet")
    return len(records)


def ensure_seeded() -> None:
    """
    Seed the SQLite database on first use to back API lookups with realistic data.
    Fails fast if, after seeding, the dataset is too small or clearly invalid.
    """
    init_db()
    engine = get_engine()
    with Session(engine) as session:
        from boardgames_api.domain.games.records import BoardgameRecord

        count = session.scalar(select(func.count(BoardgameRecord.id))) or 0
        if count >= MIN_BOARDGAMES_COUNT and not _boardgames_invalid(session):
            return

    seeded = seed_boardgames_from_parquet()

    with Session(engine) as session:
        from boardgames_api.domain.games.records import BoardgameRecord

        count = session.scalar(select(func.count(BoardgameRecord.id))) or 0
        invalid = _boardgames_invalid(session)

    if count < MIN_BOARDGAMES_COUNT or invalid:
        parquet_hint = (
            f"Expected at least {MIN_BOARDGAMES_COUNT} games but found {count}. "
            f"Ensure a valid parquet exists at {DEFAULT_PARQUET_PATH} or set "
            "BOARDGAMES_PARQUET_PATH to a populated dataset."
        )
        if invalid:
            parquet_hint += (
                " Detected invalid rows (negative metrics or placeholders); regenerate the dataset."
            )
        raise RuntimeError(
            f"Boardgame catalog not seeded properly (loaded {seeded} rows). {parquet_hint}"
        )


def _boardgames_invalid(session: Session) -> bool:
    """
    Detect obviously invalid data that would violate response schema constraints.
    """
    from boardgames_api.domain.games.records import BoardgameRecord

    min_complexity = session.scalar(select(func.min(BoardgameRecord.complexity)))
    min_age = session.scalar(select(func.min(BoardgameRecord.age_recommendation)))
    min_playtime = session.scalar(select(func.min(BoardgameRecord.playing_time_minutes)))
    min_min_players = session.scalar(select(func.min(BoardgameRecord.min_players)))
    placeholder_count = (
        session.scalar(
            select(func.count()).where(
                BoardgameRecord.title == "Valid Game",
                BoardgameRecord.description == "Good",
            )
        )
        or 0
    )
    return (
        any(
            value is not None and value < 0
            for value in (
                min_complexity,
                min_age,
            )
        )
        or any(
            value is not None and value < 1
            for value in (
                min_playtime,
                min_min_players,
            )
        )
        or placeholder_count > 0
    )
