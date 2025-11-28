from __future__ import annotations

from pathlib import Path
from typing import Optional

import polars as pl
from sqlalchemy import JSON, Float, Integer, String, create_engine, delete, func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

DATA_ROOT = Path(__file__).resolve().parents[3] / "data" / "processed"
DEFAULT_DB_PATH = DATA_ROOT / "boardgames.sqlite3"
DEFAULT_PARQUET_PATH = DATA_ROOT / "boardgames.parquet"


class Base(DeclarativeBase):
    pass


def get_engine(db_path: Path = DEFAULT_DB_PATH) -> Engine:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(f"sqlite:///{db_path}", future=True)


engine = get_engine()


class BoardgameRecord(Base):
    __tablename__ = "boardgames"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, default="")
    mechanics: Mapped[list[str]] = mapped_column(JSON, default=list)
    genre: Mapped[list[str]] = mapped_column(JSON, default=list)
    themes: Mapped[list[str]] = mapped_column(JSON, default=list)
    min_players: Mapped[int] = mapped_column(Integer)
    max_players: Mapped[int] = mapped_column(Integer)
    complexity: Mapped[Optional[float]] = mapped_column(Float, default=None)
    age_recommendation: Mapped[Optional[float]] = mapped_column(Float, default=None)
    num_user_ratings: Mapped[Optional[float]] = mapped_column(Float, default=None)
    avg_user_rating: Mapped[Optional[float]] = mapped_column(Float, default=None)
    year_published: Mapped[Optional[float]] = mapped_column(Float, default=None)
    playing_time_minutes: Mapped[int] = mapped_column(Integer)
    image_url: Mapped[str] = mapped_column(String, default="")
    bgg_url: Mapped[str] = mapped_column(String, default="")


def _coerce_list(value: object | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        parts = [part.strip() for part in value.split(",") if part.strip()]
        return parts
    return []


def _to_int(value: object | None, default: int = 0) -> int:
    if isinstance(value, (int, str)):
        try:
            return int(value)
        except (TypeError, ValueError):
            return default
    return default


def _to_float(value: object | None, default: float = 0.0) -> float:
    if isinstance(value, (int, float, str)):
        try:
            return float(value)
        except (TypeError, ValueError):
            return default
    return default


def _row_to_record(row: dict[str, object]) -> BoardgameRecord:
    return BoardgameRecord(
        id=_to_int(row.get("bgg_id")),
        title=str(row.get("name", "")),
        description=str(row.get("text_description", "") or ""),
        mechanics=_coerce_list(row.get("cat_mechanics")),
        genre=_coerce_list(row.get("cat_categories")),
        themes=_coerce_list(row.get("cat_themes")),
        min_players=_to_int(row.get("min_players"), default=1),
        max_players=_to_int(row.get("max_players"), default=1),
        complexity=_to_float(row.get("num_complexity")),
        age_recommendation=_to_float(row.get("num_age_recommendation")),
        num_user_ratings=_to_float(row.get("num_num_user_ratings")),
        avg_user_rating=_to_float(row.get("avg_rating")),
        year_published=_to_float(row.get("num_year_published")),
        playing_time_minutes=_to_int(row.get("playing_time_minutes"), default=1),
        image_url="https://example.com/placeholder.jpg",
        bgg_url=f"https://boardgamegeek.com/boardgame/{row.get('bgg_id')}",
    )


def seed_boardgames_from_parquet(
    parquet_path: Path = DEFAULT_PARQUET_PATH, db_engine: Engine | None = None
) -> int:
    """
    Load boardgame metadata from the processed parquet file into SQLite.
    Existing rows are replaced.
    """
    db_engine = db_engine or engine
    if not parquet_path.exists():
        raise FileNotFoundError(f"Processed dataset not found at {parquet_path}")

    Base.metadata.create_all(db_engine)
    df = pl.read_parquet(parquet_path)
    records = [_row_to_record(row) for row in df.to_dicts()]

    with Session(db_engine) as session:
        session.execute(delete(BoardgameRecord))
        session.add_all(records)
        session.commit()

    return len(records)


def ensure_seeded() -> None:
    """
    Seed the SQLite database on first use to back API lookups with realistic data.
    """
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        count = session.scalar(select(func.count(BoardgameRecord.id)))
        if count and count > 0:
            return
    seed_boardgames_from_parquet()
