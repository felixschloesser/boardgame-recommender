from typing import Any

from pydantic import BaseModel, Field, field_validator


class BoardgameSeedRow(BaseModel):
    bgg_id: int = Field(..., alias="bgg_id")
    name: str = Field(default="")
    text_description: str = Field(default="", alias="text_description")
    cat_mechanics: list[str] | None = Field(default=None, alias="cat_mechanics")
    cat_categories: list[str] | None = Field(default=None, alias="cat_categories")
    cat_themes: list[str] | None = Field(default=None, alias="cat_themes")
    min_players: int = Field(default=1, alias="min_players", ge=1)
    max_players: int = Field(default=1, alias="max_players", ge=1)
    num_complexity: float | None = Field(default=None, alias="num_complexity", ge=0.0, le=5.0)
    num_age_recommendation: float | None = Field(
        default=None, alias="num_age_recommendation", ge=0
    )
    num_num_user_ratings: float | None = Field(
        default=None, alias="num_num_user_ratings", ge=0
    )
    avg_rating: float | None = Field(default=None, alias="avg_rating", ge=0, le=10)
    num_year_published: float | None = Field(default=None, alias="num_year_published")
    playing_time_minutes: int = Field(default=1, alias="playing_time_minutes", ge=1)

    @field_validator(
        "bgg_id",
        "min_players",
        "max_players",
        "num_num_user_ratings",
        "num_year_published",
        "playing_time_minutes",
        mode="before",
    )
    @classmethod
    def _coerce_int(cls, value: int | float | str | None) -> int | float | None:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @field_validator(
        "num_complexity",
        "num_age_recommendation",
        "avg_rating",
        mode="before",
    )
    @classmethod
    def _coerce_float(cls, value: int | float | str | None) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

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


def row_to_record(row: dict[str, Any]):
    from boardgames_api.domain.games.models import BoardgameRecord

    seed = BoardgameSeedRow.model_validate(row)
    return BoardgameRecord(
        id=seed.bgg_id,
        title=seed.name,
        description=seed.text_description or "",
        mechanics=seed.cat_mechanics or [],
        genre=seed.cat_categories or [],
        themes=seed.cat_themes or [],
        min_players=max(1, seed.min_players),
        max_players=max(seed.min_players, seed.max_players),
        complexity=seed.num_complexity,
        age_recommendation=int(seed.num_age_recommendation or 0),
        num_user_ratings=int(seed.num_num_user_ratings or 0),
        avg_user_rating=seed.avg_rating or 0,
        year_published=int(seed.num_year_published or 0),
        playing_time_minutes=max(1, seed.playing_time_minutes),
        image_url="https://example.com/placeholder.jpg",
        bgg_url=f"https://boardgamegeek.com/boardgame/{seed.bgg_id}",
    )
