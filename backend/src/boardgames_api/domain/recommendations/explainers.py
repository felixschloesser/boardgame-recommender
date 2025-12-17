from __future__ import annotations

from typing import Iterable, List, Protocol, Tuple

import numpy as np

from boardgames_api.domain.recommendations.reccomender import ScoredGameId
from boardgames_api.domain.recommendations.schemas import (
    FeatureExplanation,
    RecommendationExplanation,
    ReferenceExplanation,
)
from boardgames_api.infrastructure.embeddings import load_embedding

_MECHANICS_KEYWORDS = [
    "acting",
    "action event",
    "action drafting",
    "action points",
    "action queue",
    "action retrieval",
    "action timer",
    "advantage token",
    "alliances",
    "area majority influence",
    "area movement",
    "area impulse",
    "auction bidding",
    "auction compensation",
    "auction: dexterity",
    "auction: dutch",
    "auction: dutch priority",
    "auction: english",
    "auction: fixed placement",
    "auction: multiple lot",
    "auction: once around",
    "auction: sealed bid",
    "auction: turn order until pass",
    "automatic resource growth",
    "betting and bluffing",
    "bingo",
    "bribery",
    "card play conflict resolution",
    "catch the leader",
    "chaining",
    "closed drafting",
    "closed economy auction",
    "contracts",
    "cooperative game",
    "deck bag and pool building",
    "deduction",
    "delayed purchase",
    "dice rolling",
    "die icon resolution",
    "enclosure",
    "end game bonuses",
    "follow",
    "grid movement",
    "hand management",
    "hidden movement",
    "hidden roles",
    "hidden victory points",
    "i cut you choose",
    "income",
    "increase value of unchosen resources",
    "investment",
    "kill steal",
    "king of the hill",
    "ladder climbing",
    "legacy game",
    "loans",
    "lose a turn",
    "mancala",
    "map addition",
    "map reduction",
    "matching",
    "memory",
    "modular board",
    "move through deck",
    "movement points",
    "multi use cards",
    "negotiation",
    "network and route building",
    "once per game abilities",
    "open drafting",
    "order counters",
    "paper and pencil",
    "pattern building",
    "pattern recognition",
    "pick up and deliver",
    "player elimination",
    "point to point movement",
    "predictive bid",
    "programmed movement",
    "push your luck",
    "race",
    "real time",
    "resource queue",
    "role playing",
    "roles with asymmetric information",
    "roll spin and move",
    "scenario mission campaign game",
    "score and reset game",
    "secret unit deployment",
    "selection order bid",
    "semi cooperative game",
    "set collection",
    "simulation",
    "simultaneous action selection",
    "solo solitaire game",
    "stacking and balancing",
    "stock holding",
    "storytelling",
    "take that",
    "targeted clues",
    "team based game",
    "tech trees tech tracks",
    "tile placement",
    "trading",
    "traitor game",
    "trick taking",
    "turn order: auction",
    "turn order: random",
    "variable player powers",
    "variable set up",
    "voting",
    "worker placement",
]

_THEME_KEYWORDS = [
    "abstract strategy",
    "action dexterity",
    "adventure",
    "american west",
    "ancient",
    "animals",
    "arabian",
    "aviation flight",
    "bluffing",
    "book",
    "card game",
    "children's game",
    "city building",
    "civilization",
    "comic book strip",
    "deduction",
    "dice",
    "economic",
    "educational",
    "electronic",
    "environmental",
    "expansion for base game",
    "exploration",
    "fantasy",
    "farming",
    "fighting",
    "game system",
    "horror",
    "humor",
    "industry manufacturing",
    "math",
    "medical",
    "medieval",
    "memory",
    "modern warfare",
    "movies tv radio theme",
    "murder mystery",
    "music",
    "mythology",
    "nautical",
    "negotiation",
    "novel based",
    "number",
    "party game",
    "pirates",
    "political",
    "prehistoric",
    "print & play",
    "puzzle",
    "racing",
    "real time",
    "renaissance",
    "science fiction",
    "space exploration",
    "spies secret agents",
    "sports",
    "territory building",
    "trains",
    "transportation",
    "travel",
    "trivia",
    "video game theme",
    "wargame",
    "word game",
    "zombies",
]

_GENRE_KEYWORDS = [
    "abstract",
    "card",
    "childrens",
    "customizable",
    "family",
    "party",
    "strategy",
    "thematic",
    "war",
]


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
        if store is None:
            return []

        id_index = {int(bgg_id): idx for idx, bgg_id in enumerate(store.bgg_ids)}
        vectors = store.vectors
        norms = store.norms
        explanations: List[RecommendationExplanation] = []
        liked_list = [int(g) for g in liked_games if int(g) in id_index]
        top_score = ranked[0].score if ranked else 0.0

        def _similarity(a_id: int, b_id: int) -> float | None:
            a_idx = id_index.get(a_id)
            b_idx = id_index.get(b_id)
            if a_idx is None or b_idx is None:
                return None
            denom = norms[a_idx] * norms[b_idx]
            if denom == 0:
                return None
            return float(np.dot(vectors[a_idx], vectors[b_idx]) / denom)

        for rank, item in enumerate(ranked):
            refs: List[ReferenceExplanation] = []
            sims: List[tuple[int, float]] = []

            for liked_id in liked_list:
                sim = _similarity(item.bgg_id, liked_id)
                if sim is not None:
                    sims.append((liked_id, sim))

            sims.sort(key=lambda t: t[1], reverse=True)
            if sims:
                # Rotate reference choices for lower-ranked items to avoid identical refs.
                if rank > 2:
                    shift = rank % len(sims)
                    sims = sims[shift:] + sims[:shift]
                sims = sims[: self.max_references]

            if not sims:
                for liked_id in liked_list[: self.max_references]:
                    refs.append(
                        ReferenceExplanation(
                            bgg_id=liked_id,
                            title=store.get_name(liked_id) or "",
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
                continue

            allow_two_positive = (
                rank < 3 or (top_score > 0 and item.score >= 0.85 * top_score)
            ) and len(sims) >= 2
            best_score = sims[0][1] or 1e-9

            for idx, (liked_id, sim) in enumerate(sims):
                rel = sim / best_score if best_score else 0.0
                if idx == 0 or (allow_two_positive and idx == 1):
                    influence = "positive"
                elif rel < 0.5 or sim < 0.15:
                    influence = "negative"
                else:
                    influence = "neutral"

                refs.append(
                    ReferenceExplanation(
                        bgg_id=liked_id,
                        title=store.get_name(liked_id) or "",
                        influence=influence,
                    )
                )

            if refs and all(r.influence == "positive" for r in refs) and len(refs) > 1:
                refs[-1] = ReferenceExplanation(
                    bgg_id=refs[-1].bgg_id,
                    title=refs[-1].title,
                    influence="neutral",
                )
            # For lower-ranked or weaker items, force at least one negative signal.
            if (
                refs
                and len(refs) > 1
                and (rank >= 3 or (top_score > 0 and item.score < 0.7 * top_score))
            ):
                refs[-1] = ReferenceExplanation(
                    bgg_id=refs[-1].bgg_id,
                    title=refs[-1].title,
                    influence="negative",
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
    Lightweight feature-based explanations using candidate metadata plus embedding
    similarity to liked games to vary influence (positive/neutral/negative).
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
        store = load_embedding()
        if store is None:
            return []

        id_index = {int(bgg_id): idx for idx, bgg_id in enumerate(store.bgg_ids)}
        vectors = store.vectors
        norms = store.norms
        explanations: List[RecommendationExplanation] = []
        boardgame_map = {bg.id: bg for bg in boardgames}
        liked_list = [int(g) for g in liked_games if int(g) in id_index]
        top_score = ranked[0].score if ranked else 0.0

        def _similarity(a_id: int, b_id: int) -> float | None:
            a_idx = id_index.get(a_id)
            b_idx = id_index.get(b_id)
            if a_idx is None or b_idx is None:
                return None
            denom = norms[a_idx] * norms[b_idx]
            if denom == 0:
                return None
            return float(np.dot(vectors[a_idx], vectors[b_idx]) / denom)

        for idx, item in enumerate(ranked):
            hints: List[FeatureExplanation] = []
            candidate = boardgame_map.get(item.bgg_id)
            if not candidate:
                explanations.append(
                    RecommendationExplanation(
                        type="features",
                        features=hints,
                        references=None,
                    )
                )
                continue

            # If we cannot compare against liked games, surface the first few features positively.
            if not liked_list:
                for label, category in self._feature_hints(candidate):
                    for token in self._split_feature_labels(label, category):
                        if len(hints) >= self.max_features:
                            break
                        hints.append(
                            FeatureExplanation(
                                label=token,
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
                continue

            sims: List[float] = []
            liked_feature_sets: dict[str, set[str]] = {
                "mechanic": set(),
                "theme": set(),
                "genre": set(),
            }
            for liked_id in liked_list:
                sim = _similarity(item.bgg_id, liked_id)
                if sim is not None:
                    sims.append(sim)
                    liked_game = boardgame_map.get(liked_id)
                    if liked_game:
                        liked_feature_sets["mechanic"].update(
                            getattr(liked_game, "mechanics", []) or []
                        )
                        liked_feature_sets["theme"].update(getattr(liked_game, "themes", []) or [])
                        liked_feature_sets["genre"].update(getattr(liked_game, "genre", []) or [])

            sims_sorted = sorted(sims, reverse=True)
            best_sim = sims_sorted[0] if sims_sorted else 0.0
            positive_count = 0

            for label, category in self._feature_hints(candidate):
                if len(hints) >= self.max_features:
                    break
                for token in self._split_feature_labels(label, category):
                    if len(hints) >= self.max_features:
                        break
                    influence = "neutral"
                    if token in liked_feature_sets.get(category, set()) and best_sim >= 0.4:
                        influence = "positive"
                    elif best_sim < 0.2:
                        influence = "negative"

                    if influence == "positive":
                        positive_count += 1

                    hints.append(
                        FeatureExplanation(
                            label=token,
                            category=category,
                            influence=influence,
                        )
                    )

            # Ensure at least one positive signal so the list does not read as all neutral/negative.
            if hints and positive_count == 0:
                hints[0] = FeatureExplanation(
                    label=hints[0].label,
                    category=hints[0].category,
                    influence="positive",
                )
                positive_count = 1

            if (
                hints
                and len(hints) > 1
                and (item.score < 0.6 * top_score or idx >= 4)
                and positive_count > 0
            ):
                # Ensure some contrast for weaker items.
                hints[-1] = FeatureExplanation(
                    label=hints[-1].label,
                    category=hints[-1].category,
                    influence="negative",
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

    def _split_feature_labels(self, label: str, category: str) -> List[str]:
        """
        Split concatenated feature strings into discrete tokens using known vocabularies.
        """
        if category == "genre":
            return [label]

        vocab = {
            "mechanic": _MECHANICS_KEYWORDS,
            "theme": _THEME_KEYWORDS,
            "genre": _GENRE_KEYWORDS,
        }.get(category, [])

        lowered = label.lower()
        tokens: List[str] = []
        for term in vocab:
            if term in lowered and term not in tokens:
                tokens.append(term)
        # Fallback to original label if nothing matched.
        return tokens or [label]


__all__ = ["Explainer", "SimilarityExplanationProvider", "FeatureHintExplanationProvider"]
