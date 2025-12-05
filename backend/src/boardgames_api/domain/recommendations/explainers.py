from __future__ import annotations

from typing import List

from boardgames_api.domain.recommendations.context import RecommendationContext, ScoredCandidate
from boardgames_api.domain.recommendations.schemas import (
    FeatureExplanation,
    RecommendationExplanation,
    ReferenceExplanation,
)


class SimilarityExplanationProvider:
    """
    Reference-based explanations using the embedding index.
    """

    def __init__(self, max_references: int = 3) -> None:
        self.max_references = max_references

    def explain(
        self, context: RecommendationContext, scored: List[ScoredCandidate]
    ) -> List[RecommendationExplanation]:
        store = context.embedding_index
        liked_ids = [int(liked) for liked in context.liked_games if store.has_id(int(liked))]

        explanations: List[RecommendationExplanation] = []
        for item in scored:
            refs: List[ReferenceExplanation] = []
            for liked_id in liked_ids[: self.max_references]:
                refs.append(
                    ReferenceExplanation(
                        bgg_id=int(liked_id),
                        title=store.get_name(int(liked_id)) or "",
                        influence="positive",
                    )
                )
            explanations.append(
                RecommendationExplanation(
                    type="references",
                    references=refs,
                    features=None,
                )
            )
        return explanations


class FeatureHintExplanationProvider:
    """
    Lightweight feature-based explanations using existing metadata.
    Provides deterministic hints without introducing a SHAP dependency.
    This is deliberately a placeholder: it always marks surfaced hints as
    positively influential and does not compute real contributions.
    """

    def __init__(self, max_features: int = 3) -> None:
        self.max_features = max_features

    def explain(
        self, context: RecommendationContext, scored: List[ScoredCandidate]
    ) -> List[RecommendationExplanation]:
        explanations: List[RecommendationExplanation] = []
        for item in scored:
            hints: List[FeatureExplanation] = []
            for label, category in self._feature_hints(item):
                hints.append(
                    FeatureExplanation(
                        label=label,
                        category=category,
                        influence="positive",
                    )
                )
                if len(hints) >= self.max_features:
                    break
            explanations.append(
                RecommendationExplanation(
                    type="features",
                    features=hints,
                    references=None,
                )
            )
        return explanations

    def _feature_hints(self, item: ScoredCandidate) -> List[tuple[str, str]]:
        game = item.candidate
        suggestions: List[tuple[str, str]] = []
        seen: set[tuple[str, str]] = set()

        def _add(label: str, category: str) -> None:
            key = (label, category)
            if label and key not in seen:
                seen.add(key)
                suggestions.append(key)

        for mechanic in game.mechanics or []:
            _add(mechanic, "mechanic")
        for theme in game.themes or []:
            _add(theme, "theme")
        for genre in game.genre or []:
            _add(genre, "genre")
        if not suggestions:
            _add(game.title, "theme")
        return suggestions
