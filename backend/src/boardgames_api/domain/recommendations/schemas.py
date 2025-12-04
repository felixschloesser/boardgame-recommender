from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from boardgames_api.domain.games.schemas import BoardGameResponse


class PlayDuration(str, Enum):
    SHORT = "short"
    MEDIUM = "medium"
    LONG = "long"

class PlayContextRequest(BaseModel):
    """Context about how the recommendation will be used."""

    model_config = ConfigDict(extra="allow")

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
        default_factory=list,
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

    @model_validator(mode="before")
    @classmethod
    def _coerce_legacy_fields(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data
        if "amount" in data and "num_results" not in data:
            data = dict(data)
            data["num_results"] = data.pop("amount")
        return data

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

    type: str = Field(description="Type of explanation (e.g., 'features', 'references').")
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
    category: str = Field(
        pattern="^(mechanic|theme|genre|playtime|complexity|age)$"
    )
    influence: str = Field(pattern="^(positive|neutral|negative)$")


# Resolve forward references
RecommendationExplanation.model_rebuild()


class Selection(BaseModel):
    """
    A single recommendation entry paired with an explanation.
    """

    boardgame: BoardGameResponse = Field(description="The recommended boardgame.")
    explanation: RecommendationExplanation = Field(
        description="Structured explanation for the recommendation.",
    )


class Recommendation(BaseModel):
    """
    A stored recommendation with intent and generated selections.
    """

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
