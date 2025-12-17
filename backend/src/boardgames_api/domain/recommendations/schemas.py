from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

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

    players: int = Field(ge=1, description="Number of players.")
    duration: PlayDuration | None = Field(
        default=None, description="Approximate session duration bucket."
    )


class RecommendationRequest(BaseModel):
    """
    Request schema for generating recommendations.
    """

    model_config = ConfigDict(extra="forbid")

    liked_games: list[int] = Field(
        description="List of game IDs the participant likes.",
        min_length=1,
    )
    play_context: PlayContextRequest = Field(
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
    def _validate_game_ids(cls, value: list[int]) -> list[int]:
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

    type: str = Field(description="Type of explanation (e.g., 'features', 'references').")
    features: list["FeatureExplanation"] | None = Field(
        default=None,
        description="Feature-based reasoning for the recommendation.",
    )
    references: list["ReferenceExplanation"] | None = Field(
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


class RecommendationResponse(BaseModel):
    """
    A stored recommendation with intent and generated selections.
    """

    model_config = ConfigDict(extra="forbid")

    id: str = Field(description="Unique identifier for the recommendation.")
    participant_id: str = Field(description="Unique identifier for the participant.")
    created_at: str = Field(description="Timestamp when the recommendation was created.")
    intent: RecommendationRequest = Field(
        description="The original request that generated the recommendations.",
    )
    model_version: str = Field(description="Version of the recommendation model used.")
    experiment_group: str = Field(description="Experiment group for the participant.")
    recommendations: list[Selection] = Field(
        description="List of generated recommendations.",
    )

    @classmethod
    def from_domain(cls, result: "RecommendationResult") -> "RecommendationResponse":
        return cls.model_validate(
            {
                "id": result.id,
                "participant_id": result.participant_id,
                "created_at": result.created_at.isoformat(),
                "intent": result.intent,
                "model_version": result.model_version,
                "experiment_group": result.experiment_group.value,
                "recommendations": [_selection_from_domain(sel) for sel in result.selections],
            }
        )


def _selection_from_domain(selection) -> dict:
    """
    Translate a domain RecommendationSelection into the API response schema shape.
    """
    return {
        "boardgame": BoardGameResponse.model_validate(
            {
                "id": str(selection.boardgame.id),
                "title": selection.boardgame.title,
                "description": selection.boardgame.description,
                "mechanics": selection.boardgame.mechanics,
                "genre": selection.boardgame.genre,
                "themes": selection.boardgame.themes,
                "min_players": selection.boardgame.min_players,
                "max_players": selection.boardgame.max_players,
                "complexity": selection.boardgame.complexity or 0,
                "age_recommendation": selection.boardgame.age_recommendation or 0,
                "num_user_ratings": selection.boardgame.num_user_ratings or 0,
                "avg_user_rating": selection.boardgame.avg_user_rating or 0,
                "year_published": selection.boardgame.year_published or 0,
                "playing_time_minutes": selection.boardgame.playing_time_minutes,
                "image_url": selection.boardgame.image_url,
                "bgg_url": selection.boardgame.bgg_url,
            }
        ),
        "explanation": selection.explanation,
    }


__all__ = [
    "RecommendationRequest",
    "RecommendationExplanation",
    "FeatureExplanation",
    "ReferenceExplanation",
    "Selection",
    "RecommendationResponse",
    "PlayContextRequest",
    "PlayDuration",
]
