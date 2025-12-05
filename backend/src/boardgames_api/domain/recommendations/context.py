from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List

from boardgames_api.domain.participants.records import StudyGroup
from boardgames_api.domain.recommendations.schemas import PlayContextRequest
from boardgames_api.utils.embedding import EmbeddingIndex


@dataclass
class RecommendationContext:
    """
    Immutable context passed to the scoring + explanation pipeline.
    Keeps domain-level inputs only; no HTTP/session side effects.
    """

    liked_games: List[int]
    play_context: PlayContextRequest
    num_results: int
    candidates: List[Any]
    participant_id: str
    study_group: StudyGroup
    embedding_index: EmbeddingIndex


@dataclass
class ScoredCandidate:
    candidate: Any
    score: float
