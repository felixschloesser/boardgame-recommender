from enum import Enum
from typing import TYPE_CHECKING, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from boardgames_api.domain.games.schemas import BoardGameResponse

if TYPE_CHECKING:
    from boardgames_api.domain.recommendations.models import RecommendationResult


class PlayDuration(str, Enum):
    SHORT = "short"
    MEDIUM = "medium"
    LONG = "long"


class PlayContextRequest(BaseModel):
    """Context about how the recommendation will be used."""

    model_config = ConfigDict(extra="forbid")

    players: Optional[int] = Field(default=None, ge=1, description="Number of players.")
    duration: Optional[PlayDuration] = Field(
        default=None,
        description="Approximate session duration bucket.",
    )


class RecommendationRequest(BaseModel):
    """
    Request schema for generating recommendations.
    """

    model_config = ConfigDict(extra="forbid")

    liked_games: List[int] = Field(
        description="List of game IDs the participant likes.",
        min_length=1,
    )
    play_context: Optional[PlayContextRequest] = Field(
        default=None,
        description="Context for the play session, including player count and duration.",
    )
    num_results: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Number of recommendations to generate.",
    )

    @field_validator("liked_games")
    @classmethod
    def _validate_game_ids(cls, value: List[int]) -> List[int]:
        if len(set(value)) != len(value):
            raise ValueError("Game IDs must be unique.")
        if any(item < 1 for item in value):
            raise ValueError("Game IDs must be positive integers.")
        return value


class RecommendationExplanation(BaseModel):
    """
    Explanation schema for why a recommendation was made.
    """

    model_config = ConfigDict(extra="forbid")

    type: str = Field(
        description="Type of explanation (e.g., 'features', 'references')."
    )
    features: Optional[List["FeatureExplanation"]] = Field(
        default=None,
        description="Feature-based reasoning for the recommendation.",
    )
    references: Optional[List["ReferenceExplanation"]] = Field(
        default=None,
        description="Reference-based reasoning using familiar games.",
    )


class ReferenceExplanation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bgg_id: int = Field(ge=1)
    title: str = Field(min_length=1)
    influence: str = Field(pattern="^(positive|neutral|negative)$")


class FeatureExplanation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = Field(min_length=1)
    category: str = Field(pattern="^(mechanic|theme|genre|playtime|complexity|age)$")
    influence: str = Field(pattern="^(positive|neutral|negative)$")


# Resolve forward references
RecommendationExplanation.model_rebuild()


class Selection(BaseModel):
    """
    A single recommendation entry paired with an explanation.
    """

    model_config = ConfigDict(extra="forbid")

    boardgame: BoardGameResponse = Field(description="The recommended boardgame.")
    explanation: RecommendationExplanation = Field(
        description="Structured explanation for the recommendation.",
    )


class Recommendation(BaseModel):
    """
    A stored recommendation with intent and generated selections.
    """

    model_config = ConfigDict(extra="forbid")

    id: str = Field(description="Unique identifier for the recommendation.")
    participant_id: str = Field(description="Unique identifier for the participant.")
    created_at: str = Field(
        description="Timestamp when the recommendation was created."
    )
    intent: RecommendationRequest = Field(
        description="The original request that generated the recommendations.",
    )
    model_version: str = Field(description="Version of the recommendation model used.")
    experiment_group: str = Field(description="Experiment group for the participant.")
    recommendations: List[Selection] = Field(
        description="List of generated recommendations.",
    )

    @classmethod
    def from_domain(cls, result: "RecommendationResult") -> "Recommendation":
        return cls.model_validate(
            {
                "id": result.id,
                "participant_id": result.participant_id,
                "created_at": result.created_at.isoformat(),
                "intent": result.intent,
                "model_version": result.model_version,
                "experiment_group": result.experiment_group.value,
                "recommendations": [
                    {
                        "boardgame": BoardGameResponse.model_validate(
                            {
                                "id": str(sel.boardgame.id),
                                "title": sel.boardgame.title,
                                "description": sel.boardgame.description,
                                "mechanics": sel.boardgame.mechanics,
                                "genre": sel.boardgame.genre,
                                "themes": sel.boardgame.themes,
                                "min_players": sel.boardgame.min_players,
                                "max_players": sel.boardgame.max_players,
                                "complexity": sel.boardgame.complexity or 0,
                                "age_recommendation": sel.boardgame.age_recommendation or 0,
                                "num_user_ratings": sel.boardgame.num_user_ratings or 0,
                                "avg_user_rating": sel.boardgame.avg_user_rating or 0,
                                "year_published": sel.boardgame.year_published or 0,
                                "playing_time_minutes": sel.boardgame.playing_time_minutes,
                                "image_url": sel.boardgame.image_url,
                                "bgg_url": sel.boardgame.bgg_url,
                            }
                        ),
                        "explanation": sel.explanation,
                    }
                    for sel in result.selections
                ],
            }
        )
