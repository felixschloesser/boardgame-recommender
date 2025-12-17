from __future__ import annotations

from typing import Iterable, List, Protocol, Tuple

from boardgames_api.domain.recommendations.reccomender import ScoredGameId
from boardgames_api.domain.recommendations.schemas import (
    FeatureExplanation,
    RecommendationExplanation,
    ReferenceExplanation,
)
from boardgames_api.infrastructure.embeddings import load_embedding


class Explainer(Protocol):
    def add_explanations(
        self,
        ranked: List[ScoredGameId],
        liked_games: Iterable[int],
        boardgames: Iterable = (),
    ) -> List[RecommendationExplanation]: ...


class SimilarityExplanationProvider(Explainer):
    """
    Reference-based explanations using liked games and embedding metadata.
    """

    def __init__(
        self,
        max_references: int = 3,
    ) -> None:
        self.max_references = max_references

    def add_explanations(
        self,
        ranked: List[ScoredGameId],
        liked_games: Iterable[int],
        boardgames: Iterable = (),
    ) -> List[RecommendationExplanation]:
        store = load_embedding()
        explanations: List[RecommendationExplanation] = []
        liked_list = [int(g) for g in liked_games]
        for _item in ranked:
            refs: List[ReferenceExplanation] = []
            for liked_id in liked_list[: self.max_references]:
                refs.append(
                    ReferenceExplanation(
                        bgg_id=liked_id,
                        title=store.get_name(liked_id) or "" if store else "",
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


class FeatureHintExplanationProvider(Explainer):
    """
    Lightweight feature-based explanations using candidate metadata.
    """

    def __init__(
        self,
        max_features: int = 3,
    ) -> None:
        self.max_features = max_features

    def add_explanations(
        self,
        ranked: List[ScoredGameId],
        liked_games: Iterable[int],
        boardgames: Iterable = (),
    ) -> List[RecommendationExplanation]:
        explanations: List[RecommendationExplanation] = []
        boardgame_map = {bg.id: bg for bg in boardgames}
        for item in ranked:
            hints: List[FeatureExplanation] = []
            for label, category in self._feature_hints(boardgame_map.get(item.bgg_id)):
                if len(hints) >= self.max_features:
                    break
                hints.append(
                    FeatureExplanation(
                        label=label,
                        category=category,
                        influence="positive",
                    )
                )
            explanations.append(
                RecommendationExplanation(
                    type="features",
                    features=hints,
                    references=None,
                )
            )
        return explanations

    def _feature_hints(self, game) -> List[Tuple[str, str]]:
        suggestions: List[Tuple[str, str]] = []
        seen: set[Tuple[str, str]] = set()

        def _add(label: str, category: str) -> None:
            key = (label, category)
            if label and key not in seen:
                seen.add(key)
                suggestions.append(key)

        for mechanic in getattr(game, "mechanics", []) or []:
            _add(mechanic, "mechanic")
        for theme in getattr(game, "themes", []) or []:
            _add(theme, "theme")
        for genre in getattr(game, "genre", []) or []:
            _add(genre, "genre")
        if not suggestions:
            _add(getattr(game, "title", ""), "theme")
        return suggestions


__all__ = ["Explainer", "SimilarityExplanationProvider", "FeatureHintExplanationProvider"]
