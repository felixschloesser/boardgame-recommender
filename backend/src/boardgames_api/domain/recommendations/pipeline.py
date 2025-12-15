from __future__ import annotations

from typing import Any, List, Protocol

from sqlalchemy.orm import Session

from boardgames_api.domain.games.schemas import BoardGameResponse
from boardgames_api.domain.recommendations.context import RecommendationContext, ScoredCandidate
from boardgames_api.domain.recommendations.schemas import RecommendationExplanation, Selection


class Scorer(Protocol):
    def score(self, context: RecommendationContext) -> List[ScoredCandidate]: ...


class Explainer(Protocol):
    def explain(
        self,
        context: RecommendationContext,
        scored: List[ScoredCandidate],
        db: Session,
    ) -> List[RecommendationExplanation]: ...


def run_pipeline(
    *,
    context: RecommendationContext,
    scorer: Scorer,
    explainer: Explainer,
    db: Session,
) -> List[Selection]:
    scored = scorer.score(context)
    ranked = sorted(scored, key=lambda item: item.score, reverse=True)
    top = ranked[: context.num_results]

    explanations = explainer.explain(context, top, db)
    results: List[Selection] = []
    for item, explanation in zip(top, explanations):
        results.append(
            Selection(
                boardgame=_to_boardgame_response(item.candidate),
                explanation=explanation,
            )
        )
    return results


def _to_boardgame_response(candidate: Any) -> BoardGameResponse:
    if isinstance(candidate, BoardGameResponse):
        return candidate
    # Assume ORM-like object with expected attributes
    data = {
        "id": str(getattr(candidate, "id")),
        "title": getattr(candidate, "title"),
        "description": getattr(candidate, "description", ""),
        "mechanics": getattr(candidate, "mechanics", []) or [],
        "genre": getattr(candidate, "genre", []) or [],
        "themes": getattr(candidate, "themes", []) or [],
        "min_players": getattr(candidate, "min_players"),
        "max_players": getattr(candidate, "max_players"),
        "complexity": getattr(candidate, "complexity", 0) or 0,
        "age_recommendation": getattr(candidate, "age_recommendation", 0) or 0,
        "num_user_ratings": getattr(candidate, "num_user_ratings", 0) or 0,
        "avg_user_rating": getattr(candidate, "avg_user_rating", 0) or 0,
        "year_published": getattr(candidate, "year_published", 0) or 0,
        "playing_time_minutes": getattr(candidate, "playing_time_minutes"),
        "image_url": getattr(candidate, "image_url", ""),
        "bgg_url": getattr(candidate, "bgg_url", ""),
    }
    return BoardGameResponse.model_validate(data)
