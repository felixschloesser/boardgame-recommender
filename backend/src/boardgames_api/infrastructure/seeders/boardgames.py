from typing import Any

from pydantic import BaseModel, Field, field_validator


class BoardgameSeedRow(BaseModel):
    bgg_id: int = Field(..., alias="bgg_id")
    name: str = Field(default="")
    text_description: str = Field(default="", alias="text_description")

    cat_mechanics: list[str] | None = Field(default=None, alias="cat_mechanics")
    cat_categories: list[str] | None = Field(default=None, alias="cat_categories")
    cat_themes: list[str] | None = Field(default=None, alias="cat_themes")

    min_players: int = Field(default=1, alias="min_players")
    max_players: int = Field(default=1, alias="max_players")
    playing_time_minutes: int = Field(default=1, alias="playing_time_minutes")

    complexity: float | None = Field(default=None, alias="complexity")
    age_recommendation: float | None = Field(default=None, alias="age_recommendation")
    num_user_ratings: int | float | None = Field(default=None, alias="num_user_ratings")
    year_published: int | float | None = Field(default=None, alias="year_published")
    avg_rating: float | None = Field(default=None, alias="avg_rating")

    model_config = {"extra": "allow"}

    @field_validator("cat_mechanics", "cat_categories", "cat_themes", mode="before")
    @classmethod
    def _split_tags(cls, value: object) -> list[str] | None:
        if value is None:
            return None
        if isinstance(value, list):
            return [str(v) for v in value if str(v).strip()]
        if isinstance(value, str):
            parts = [part.strip() for part in value.split(",") if part.strip()]
            return parts
        return None

    @field_validator("bgg_id", "min_players", "max_players", "playing_time_minutes", mode="before")
    @classmethod
    def _coerce_int(cls, value: int | float | str | None) -> int | None:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @field_validator("min_players", "max_players", "playing_time_minutes", mode="after")
    @classmethod
    def _clamp_positive_int(cls, value: int | None) -> int:
        try:
            return max(1, int(value or 0))
        except Exception:
            return 1

    @field_validator("complexity", "age_recommendation", "avg_rating", mode="before")
    @classmethod
    def _coerce_float(cls, value: int | float | str | None) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @field_validator("complexity", mode="after")
    @classmethod
    def _clamp_complexity(cls, value: float | None) -> float | None:
        if value is None:
            return None
        return max(0.0, min(5.0, value))

    @field_validator("age_recommendation", mode="after")
    @classmethod
    def _clamp_age(cls, value: float | None) -> float | None:
        if value is None:
            return None
        return max(0.0, value)

    @field_validator("avg_rating", mode="after")
    @classmethod
    def _clamp_rating(cls, value: float | None) -> float | None:
        if value is None:
            return None
        return max(0.0, min(10.0, value))

    @field_validator("num_user_ratings", mode="before")
    @classmethod
    def _coerce_counts(cls, value: int | float | str | None) -> int | None:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @field_validator("num_user_ratings", mode="after")
    @classmethod
    def _clamp_counts(cls, value: int | None) -> int | None:
        if value is None:
            return None
        try:
            return max(0, int(value))
        except Exception:
            return 0


def row_to_record(row: dict[str, Any]):
    from boardgames_api.domain.games.records import BoardgameRecord

    seed = BoardgameSeedRow.model_validate(row)

    description = ""
    if "description" in row:
        try:
            description = str(row.get("description") or "")
        except Exception:
            description = ""

    min_p = max(1, seed.min_players or 1)
    max_p = max(min_p, seed.max_players or min_p)
    play_time = max(1, seed.playing_time_minutes or 1)

    return BoardgameRecord(
        id=seed.bgg_id,
        title=seed.name,
        description=description,
        mechanics=seed.cat_mechanics or [],
        genre=seed.cat_categories or [],
        themes=seed.cat_themes or [],
        min_players=min_p,
        max_players=max_p,
        complexity=seed.complexity,
        age_recommendation=int(seed.age_recommendation or 0),
        num_user_ratings=int(seed.num_user_ratings or 0),
        avg_user_rating=seed.avg_rating or 0,
        year_published=int(seed.year_published or 0),
        playing_time_minutes=play_time,
        image_url="https://example.com/placeholder.jpg",
        bgg_url=f"https://boardgamegeek.com/boardgame/{seed.bgg_id}",
    )
