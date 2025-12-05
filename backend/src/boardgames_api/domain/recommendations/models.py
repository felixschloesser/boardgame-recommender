from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List

from boardgames_api.domain.games.records import BoardgameRecord
from boardgames_api.domain.participants.records import StudyGroup
from boardgames_api.domain.recommendations.schemas import (
    RecommendationExplanation,
    RecommendationRequest,
)


@dataclass(frozen=True)
class RecommendationSelection:
    boardgame: BoardgameRecord
    explanation: RecommendationExplanation


@dataclass(frozen=True)
class RecommendationResult:
    id: str
    participant_id: str
    created_at: datetime
    intent: RecommendationRequest
    model_version: str
    experiment_group: StudyGroup
    selections: List[RecommendationSelection]


__all__ = ["RecommendationSelection", "RecommendationResult"]
