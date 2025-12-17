from typing import List

from pydantic import BaseModel, ConfigDict, Field


class BoardGameResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int = Field(..., description="Unique identifier for the boardgame.")
    title: str = Field(..., description="Title of the boardgame.")
    description: str = Field(..., description="Description of the boardgame.")
    mechanics: List[str] = Field(
        default_factory=list, description="List of mechanics used in the game."
    )
    genre: List[str] = Field(
        default_factory=list, description="List of genres the game belongs to."
    )
    themes: List[str] = Field(
        default_factory=list, description="List of themes associated with the game."
    )
    min_players: int = Field(..., ge=1, description="Minimum number of players required.")
    max_players: int = Field(..., ge=1, description="Maximum number of players allowed.")
    complexity: float = Field(..., ge=0, le=5, description="Complexity rating of the game (0-5).")
    age_recommendation: int = Field(..., ge=0, description="Recommended minimum age to play.")
    num_user_ratings: int = Field(..., ge=0, description="Number of user ratings.")
    avg_user_rating: float = Field(..., ge=0, le=10, description="Average user rating (0-10).")
    year_published: int = Field(..., description="Year the game was published.")
    playing_time_minutes: int = Field(..., ge=1, description="Average playing time in minutes.")
    image_url: str = Field(..., description="URL of the boardgame's image.")
    bgg_url: str = Field(..., description="URL to the boardgame's page on BoardGameGeek.")

    @classmethod
    def from_record(cls, record: object) -> "BoardGameResponse":
        """
        Construct a response from an ORM record without duplicating normalization.
        """
        data = {
            "id": int(getattr(record, "id")),
            "title": getattr(record, "title"),
            "description": getattr(record, "description"),
            "mechanics": getattr(record, "mechanics", []) or [],
            "genre": getattr(record, "genre", []) or [],
            "themes": getattr(record, "themes", []) or [],
            "min_players": getattr(record, "min_players"),
            "max_players": getattr(record, "max_players"),
            "complexity": getattr(record, "complexity", 0) or 0,
            "age_recommendation": getattr(record, "age_recommendation", 0) or 0,
            "num_user_ratings": getattr(record, "num_user_ratings", 0) or 0,
            "avg_user_rating": getattr(record, "avg_user_rating", 0) or 0,
            "year_published": getattr(record, "year_published", 0) or 0,
            "playing_time_minutes": getattr(record, "playing_time_minutes"),
            "image_url": getattr(record, "image_url"),
            "bgg_url": getattr(record, "bgg_url"),
        }
        return cls.model_validate(data)

    @property
    def bgg_id(self) -> int:
        """
        Integer form of the boardgame id for downstream domain logic.
        """
        return int(self.id)


class PaginatedBoardGamesResponse(BaseModel):
    """
    Pagination envelope for boardgame listings.
    """

    model_config = ConfigDict(extra="forbid")

    total: int = Field(..., ge=0, description="Total number of items available.")
    limit: int = Field(..., ge=1, le=100, description="Number of items per page.")
    offset: int = Field(..., ge=0, description="Offset for pagination.")
    items: List[BoardGameResponse] = Field(
        ..., description="List of boardgames for the current page."
    )


class BoardGamesQuery(BaseModel):
    """
    Query parameters for listing boardgames.
    """

    model_config = ConfigDict(extra="forbid")

    limit: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Number of items per page.",
    )
    offset: int = Field(
        default=0,
        ge=0,
        description="Offset for pagination.",
    )
    genre: List[str] | None = Field(default=None, description="Filter by genre.")
    mechanics: List[str] | None = Field(default=None, description="Filter by mechanics.")
    themes: List[str] | None = Field(default=None, description="Filter by themes.")
    q: str | None = Field(default=None, description="Search query for boardgame titles.")
