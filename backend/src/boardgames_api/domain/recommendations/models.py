from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List, Sequence

from boardgames_api.domain.games.records import BoardgameRecord
from boardgames_api.domain.participants.records import StudyGroup
from boardgames_api.domain.recommendations.reccomender import ScoredGameId
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

    @classmethod
    def from_ranked(
        cls,
        request: RecommendationRequest,
        participant_id: str,
        study_group: StudyGroup,
        ranked: Sequence[ScoredGameId],
        explanations: Sequence[RecommendationExplanation],
        model_version: str,
        rec_id: str,
        created_at: datetime,
        boardgames: Sequence[BoardgameRecord],
    ) -> "RecommendationResult":
        boardgame_map = {bg.id: bg for bg in boardgames}
        selections: List[RecommendationSelection] = []
        for item, explanation in zip(ranked, explanations):
            bg = boardgame_map.get(item.bgg_id)
            if not bg:
                continue
            selections.append(
                RecommendationSelection(
                    boardgame=bg,
                    explanation=explanation,
                )
            )

        return cls(
            id=rec_id,
            participant_id=participant_id,
            created_at=created_at,
            intent=request,
            model_version=model_version,
            experiment_group=study_group,
            selections=selections,
        )


__all__ = ["RecommendationSelection", "RecommendationResult"]
