from __future__ import annotations

from typing import List

from boardgames_api.domain.recommendations.context import RecommendationContext, ScoredCandidate
from boardgames_api.domain.recommendations.exceptions import RecommendationUnavailableError


class EmbeddingScorer:
    """
    Scores candidates based on similarity to liked games using the embedding index.
    """

    def score(self, context: RecommendationContext) -> List[ScoredCandidate]:
        store = context.embedding_index
        if store is None:
            raise RecommendationUnavailableError(
                "Embedding store is not available; "
                "train and load embeddings before requesting recommendations."
            )

        liked_ids = [int(liked) for liked in context.liked_games if store.has_id(int(liked))]
        if not liked_ids:
            raise RecommendationUnavailableError(
                "No embeddings available for the liked games; "
                "choose games that exist in the dataset."
            )

        def _cid(obj) -> int:
            return int(getattr(obj, "id"))

        candidate_ids = []
        for game in context.candidates:
            cid = _cid(game)
            if store.has_id(cid) and cid not in liked_ids:
                candidate_ids.append(cid)
        if not candidate_ids:
            raise RecommendationUnavailableError(
                "No candidate games with embeddings matched the filters; "
                "try adjusting constraints or regenerating embeddings."
            )

        scores = store.score_candidates(liked_ids, candidate_ids)
        if not scores:
            raise RecommendationUnavailableError(
                "Unable to score candidates with the current embeddings; retrain or adjust inputs."
            )

        scored: List[ScoredCandidate] = []
        for candidate in context.candidates:
            candidate_id = _cid(candidate)
            if candidate_id in liked_ids:
                continue
            score = scores.get(candidate_id)
            if score is None:
                continue
            scored.append(ScoredCandidate(candidate=candidate, score=float(score)))

        return sorted(scored, key=lambda item: item.score, reverse=True)
