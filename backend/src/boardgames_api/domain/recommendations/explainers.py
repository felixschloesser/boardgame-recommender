from __future__ import annotations

from typing import List

from sqlalchemy.orm import Session

from boardgames_api.domain.games.exceptions import GameNotFoundError
from boardgames_api.domain.games.service import get_boardgame
from boardgames_api.domain.recommendations.constants import GENRE_LIST, MECHANICS_LIST, THEME_LIST
from boardgames_api.domain.recommendations.context import RecommendationContext, ScoredCandidate
from boardgames_api.domain.recommendations.schemas import (
    FeatureExplanation,
    RecommendationExplanation,
    ReferenceExplanation,
)
from boardgames_api.domain.recommendations.scoring import EmbeddingScorer


class SimilarityExplanationProvider:
    """
    Reference-based explanations using the embedding index.
    """

    def __init__(
        self,
        max_references: int = 3,
        neutral_threshold: float = 0.33,
        positive_threshold: float = 0.66,
    ) -> None:
        self.max_references = max_references
        self.neutral_threshold = neutral_threshold
        self.positive_threshold = positive_threshold

    def explain(
        self,
        context: RecommendationContext,
        scored: List[ScoredCandidate],
        db: Session,
    ) -> List[RecommendationExplanation]:
        store = context.embedding_index
        liked_ids = [int(liked) for liked in context.liked_games if store.has_id(int(liked))]
        liked_games_data: list[tuple[int, object | None]] = []
        for liked_id in liked_ids:
            try:
                liked_games_data.append((liked_id, get_boardgame(liked_id, db)))
            except GameNotFoundError:
                liked_games_data.append((liked_id, None))
        explanations: List[RecommendationExplanation] = []
        scorer = EmbeddingScorer()
        for item in scored:
            explanations_scored_sorted: List[ScoredCandidate] = []
            refs: List[ReferenceExplanation] = []
            for liked_id, liked_game_response in liked_games_data:
                if liked_game_response is None:
                    refs.append(
                        ReferenceExplanation(
                            bgg_id=int(liked_id),
                            title=store.get_name(int(liked_id)) or "",
                            influence="positive",
                        )
                    )
                    continue
                explanation_context = RecommendationContext(
                    liked_games=[item.candidate.id],
                    play_context=context.play_context,
                    num_results=1,
                    candidates=[liked_game_response],
                    participant_id=context.participant_id,
                    study_group=context.study_group,
                    embedding_index=context.embedding_index,
                )

                explanation_scored = scorer.score(explanation_context)
                explanations_scored_sorted.append(explanation_scored[0])

            explanations_scored_sorted.sort(reverse=True, key=lambda exp: exp.score)

            for exp in explanations_scored_sorted[: self.max_references]:
                if exp.score < self.neutral_threshold:
                    influence = "negative"
                elif exp.score < self.positive_threshold:
                    influence = "neutral"
                else:
                    influence = "positive"

                refs.append(
                    ReferenceExplanation(
                        bgg_id=int(exp.candidate.id),
                        title=store.get_name(int(exp.candidate.id)) or "",
                        influence=influence,
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

    def __init__(self, max_features: int = 3, min_relevance_score: float = 0.5) -> None:
        self.max_features = max_features
        self.min_relevance_score = min_relevance_score

    def explain(
        self,
        context: RecommendationContext,
        scored: List[ScoredCandidate],
        db: Session,
    ) -> List[RecommendationExplanation]:
        explanations: List[RecommendationExplanation] = []
        scorer = EmbeddingScorer()
        liked_games_data: list[tuple[int, object | None]] = []
        for liked_id in context.liked_games:
            try:
                liked_games_data.append((liked_id, get_boardgame(liked_id, db)))
            except GameNotFoundError:
                liked_games_data.append((liked_id, None))
        for item in scored:
            # Collect all features from liked games that contributed to the recommendation
            relevant_features_collection: List[tuple[str, str]] = []
            for liked_id, liked_game_response in liked_games_data:
                if liked_game_response is None:
                    continue
                explanation_context = RecommendationContext(
                    liked_games=[item.candidate.id],
                    play_context=context.play_context,
                    num_results=1,
                    candidates=[liked_game_response],
                    participant_id=context.participant_id,
                    study_group=context.study_group,
                    embedding_index=context.embedding_index,
                )
                explanation_scored = scorer.score(explanation_context)
                if explanation_scored[0].score >= self.min_relevance_score:
                    relevant_features_collection.extend(self._feature_hints(explanation_scored[0]))

            hints: List[FeatureExplanation] = []
            for label, category in self._feature_hints(item):
                complete_labels = []
                searchList = []
                if category == "mechanic":
                    searchList = MECHANICS_LIST
                elif category == "theme":
                    searchList = THEME_LIST
                else:
                    searchList = GENRE_LIST

                split_labels = label.split()
                index = 0
                while index < len(split_labels):

                    def check_occurance(
                        optionList: List[str],
                        searchList: List[str],
                        startindex: int,
                        currentindex: int,
                    ) -> int:
                        searchList_string = "/".join(searchList)
                        searchword = " ".join(optionList[startindex : currentindex + 1])
                        searchword_plus_one = " ".join(optionList[startindex : currentindex + 2])
                        if (
                            (searchword in searchList_string)
                            and (searchword_plus_one not in searchList_string)
                        ) or (searchword == searchword_plus_one):
                            return currentindex + 1
                        else:
                            return check_occurance(
                                optionList, searchList, startindex, currentindex + 1
                            )

                    if category == "genre":
                        if split_labels[index] in searchList:
                            complete_labels.append(split_labels[index])
                        index += 1
                    else:
                        split_index = check_occurance(split_labels, searchList, index, index)
                        complete_label = " ".join(split_labels[index:split_index])
                        complete_labels.append(complete_label)
                        index = split_index

                relevant_tuple: tuple[str, str] | None = None
                for tuple_item in relevant_features_collection:
                    if tuple_item[1] == category:
                        relevant_tuple = tuple_item

                for full_label in complete_labels:
                    is_relevant = (
                        relevant_tuple is not None
                        and category == relevant_tuple[1]
                        and full_label in relevant_tuple[0]
                    )
                    influence = "positive" if is_relevant else "negative"
                    hints.append(
                        FeatureExplanation(
                            label=full_label,
                            category=category,
                            influence=influence,
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
