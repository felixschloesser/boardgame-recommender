from typing import List, Optional

from pydantic import BaseModel, Field, model_validator

from boardgames_api.models.games import BoardGame


class PlayContext(BaseModel):
    """Context about how the recommendation will be used."""

    players: Optional[int] = Field(default=None, description="Number of players.")
    duration: Optional[str] = Field(
        default=None,
        description="Approximate session duration bucket.",
    )


class RecommendationRequest(BaseModel):
    """
    Request schema for generating recommendations.
    Accepts both the shape defined in the OpenAPI spec and the simplified test payload.
    """

    liked_games: List[int] = Field(
        default_factory=list,
        description="List of game IDs the participant likes.",
    )
    disliked_games: List[int] = Field(
        default_factory=list,
        description="List of game IDs the participant dislikes.",
    )
    play_context: Optional[PlayContext] = Field(
        default=None,
        description="Context for the play session, including player count and duration.",
    )
    preference_tags: List[str] = Field(
        default_factory=list,
        description="Tags representing participant preferences.",
    )
    avoid_tags: List[str] = Field(
        default_factory=list,
        description="Tags representing participant dislikes.",
    )
    num_results: int = Field(
        default=10,
        description="Number of recommendations to generate.",
    )
    # Additional fields accepted by the integration tests; normalized in a validator.
    player_count: Optional[int] = Field(
        default=None,
        description="Requested player count (test payload field).",
        exclude=True,
    )
    available_time_minutes: Optional[int] = Field(
        default=None,
        description="Available time in minutes (test payload field).",
        exclude=True,
    )
    amount: Optional[int] = Field(
        default=None,
        description="Alias for num_results used in tests.",
        exclude=True,
    )

    @model_validator(mode="after")
    def normalize_fields(self) -> "RecommendationRequest":
        """
        Harmonize alternative payload shapes into the canonical fields.
        """
        if self.amount is not None:
            self.num_results = self.amount

        if self.play_context is None and (
            self.player_count is not None or self.available_time_minutes is not None
        ):
            duration: Optional[str] = None
            if self.available_time_minutes is not None:
                if self.available_time_minutes <= 30:
                    duration = "short"
                elif self.available_time_minutes <= 90:
                    duration = "medium"
                else:
                    duration = "long"

            self.play_context = PlayContext(
                players=self.player_count, duration=duration
            )

        return self


class RecommendationExplanation(BaseModel):
    """
    Explanation schema for why a recommendation was made.
    """

    type: str = Field(description="Type of explanation (e.g., 'features', 'references').")
    features: Optional[List[dict[str, str]]] = Field(
        default=None,
        description="Feature-based reasoning for the recommendation.",
    )
    references: Optional[List[dict[str, str]]] = Field(
        default=None,
        description="Reference-based reasoning using familiar games.",
    )


class Recommendation(BaseModel):
    """
    A single recommendation entry paired with an explanation.
    """

    boardgame: BoardGame = Field(description="The recommended boardgame.")
    explanation: RecommendationExplanation = Field(
        description="Structured explanation for the recommendation.",
    )


class RecommendationResponse(BaseModel):
    """
    Response schema for a recommendation session.
    """

    session_id: str = Field(description="Unique identifier for the recommendation session.")
    participant_id: str = Field(description="Unique identifier for the participant.")
    created_at: str = Field(description="Timestamp when the session was created.")
    intent: RecommendationRequest = Field(
        description="The original request that generated the recommendations.",
    )
    model_version: str = Field(description="Version of the recommendation model used.")
    experiment_group: str = Field(description="Experiment group for the participant.")
    recommendations: List[Recommendation] = Field(
        description="List of generated recommendations.",
    )
