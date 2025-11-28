from typing import List

from pydantic import BaseModel, Field


class BoardGame(BaseModel):
    id: str = Field(..., description="Unique identifier for the boardgame.")
    title: str = Field(..., description="Title of the boardgame.")
    description: str = Field(..., description="Description of the boardgame.")
    mechanics: List[str] = Field(default=[], description="List of mechanics used in the game.")
    genre: List[str] = Field(default=[], description="List of genres the game belongs to.")
    themes: List[str] = Field(default=[], description="List of themes associated with the game.")
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


class Paginated(BaseModel):
    total: int = Field(..., ge=0, description="Total number of items available.")
    limit: int = Field(..., ge=1, le=100, description="Number of items per page.")
    offset: int = Field(..., ge=0, description="Offset for pagination.")
    items: List[BoardGame] = Field(..., description="List of boardgames for the current page.")
