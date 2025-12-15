from __future__ import annotations

from typing import cast

import pytest
from boardgames_api.domain.games.schemas import BoardGameResponse
from boardgames_api.domain.participants.records import StudyGroup
from boardgames_api.domain.recommendations.context import RecommendationContext, ScoredCandidate
from boardgames_api.domain.recommendations.explainers import (
    FeatureHintExplanationProvider,
    SimilarityExplanationProvider,
)
from boardgames_api.domain.recommendations.pipeline import run_pipeline
from boardgames_api.domain.recommendations.schemas import (
    PlayContextRequest,
    RecommendationExplanation,
)
from boardgames_api.domain.recommendations.scoring import EmbeddingScorer
from boardgames_api.domain.recommendations.service import _select_explainer
from sqlalchemy.orm import Session


class _FakeStore:
    def __init__(self) -> None:
        self.names = {}

    def has_id(self, bgg_id: int) -> bool:
        return True

    def score_candidates(self, liked_ids, candidate_ids):  # type: ignore[no-untyped-def]
        # deterministic score: candidate id itself
        return {int(cid): float(cid) for cid in candidate_ids}

    def get_name(self, bgg_id: int):
        return f"Game {bgg_id}"


class _ScoringStore:
    """Embedding store with deterministic scores per candidate id."""

    def __init__(self, scores: dict[int, float]) -> None:
        self.scores = scores

    def has_id(self, bgg_id: int) -> bool:
        return True

    def score_candidates(self, liked_ids, candidate_ids):  # type: ignore[no-untyped-def]
        return {int(cid): float(self.scores.get(int(cid), 0.0)) for cid in candidate_ids}

    def get_name(self, bgg_id: int):
        return f"Game {bgg_id}"


def _game(game_id: int, *, mechanics=None, themes=None, genre=None) -> BoardGameResponse:
    return BoardGameResponse(
        id=str(game_id),
        title=f"Game {game_id}",
        description="desc",
        mechanics=mechanics or [],
        genre=genre or [],
        themes=themes or [],
        min_players=2,
        max_players=4,
        complexity=1.0,
        age_recommendation=8,
        num_user_ratings=0,
        avg_user_rating=0.0,
        year_published=2020,
        playing_time_minutes=30,
        image_url="http://example.com",
        bgg_url="http://example.com",
    )


def test_scorer_excludes_liked_and_ranks_desc():
    store = _FakeStore()
    context = RecommendationContext(
        liked_games=[1],
        play_context=PlayContextRequest(),
        num_results=3,
        candidates=[_game(1), _game(2), _game(3)],
        participant_id="p",
        study_group=StudyGroup.REFERENCES,
        embedding_index=store,
    )
    scorer = EmbeddingScorer()
    scored = scorer.score(context)
    ids = [s.candidate.id for s in scored]
    assert ids == ["3", "2"]  # liked id excluded, sorted by score (id value)


def test_similarity_explainer_uses_liked_refs(monkeypatch):
    store = _FakeStore()
    monkeypatch.setattr(
        "boardgames_api.domain.recommendations.explainers.get_boardgame",
        lambda bgg_id, db: _game(bgg_id),
    )
    context = RecommendationContext(
        liked_games=[10, 11],
        play_context=PlayContextRequest(),
        num_results=1,
        candidates=[_game(2)],
        participant_id="p",
        study_group=StudyGroup.REFERENCES,
        embedding_index=store,
    )
    scored = [ScoredCandidate(candidate=_game(2), score=1.0)]
    explainer = SimilarityExplanationProvider(max_references=1)
    explanations = explainer.explain(context, scored, db=cast(Session, object()))
    assert explanations and explanations[0].type == "references"
    refs = explanations[0].references or []
    assert len(refs) == 1
    assert refs[0].bgg_id in {10, 11}


def test_feature_explainer_prioritizes_mechanics_then_themes_genre(monkeypatch):
    store = _FakeStore()
    monkeypatch.setattr(
        "boardgames_api.domain.recommendations.explainers.get_boardgame",
        lambda bgg_id, db: _game(
            int(bgg_id), mechanics=["Deck"], themes=["Space"], genre=["Strategy"]
        ),
    )
    context = RecommendationContext(
        liked_games=[1],
        play_context=PlayContextRequest(),
        num_results=1,
        candidates=[_game(5, mechanics=["Deck"], themes=["Space"], genre=["Strategy"])],
        participant_id="p",
        study_group=StudyGroup.FEATURES,
        embedding_index=store,
    )
    scored = [ScoredCandidate(candidate=context.candidates[0], score=1.0)]
    explainer = FeatureHintExplanationProvider(max_features=2)
    explanations = explainer.explain(context, scored, db=cast(Session, object()))
    features = explanations[0].features or []
    assert [f.label for f in features] == ["Deck", "Space"]
    assert all(
        f.type == "features" if isinstance(f, RecommendationExplanation) else True
        for f in explanations
    )


def test_pipeline_limits_results_and_pairs_explanations(monkeypatch):
    store = _FakeStore()
    monkeypatch.setattr(
        "boardgames_api.domain.recommendations.explainers.get_boardgame",
        lambda bgg_id, db: _game(int(bgg_id)),
    )
    context = RecommendationContext(
        liked_games=[1],
        play_context=PlayContextRequest(),
        num_results=1,
        candidates=[_game(2), _game(3)],
        participant_id="p",
        study_group=StudyGroup.REFERENCES,
        embedding_index=store,
    )
    scorer = EmbeddingScorer()
    explainer = SimilarityExplanationProvider()
    selections = run_pipeline(
        context=context, scorer=scorer, explainer=explainer, db=cast(Session, object())
    )
    assert len(selections) == 1
    assert selections[0].boardgame.id == "3"  # highest score
    assert selections[0].explanation.type == "references"


@pytest.mark.parametrize(
    "group,expected_cls",
    [
        (StudyGroup.FEATURES, FeatureHintExplanationProvider),
        (StudyGroup.REFERENCES, SimilarityExplanationProvider),
    ],
)
def test_select_explainer_mapping(group, expected_cls):
    explainer = _select_explainer(group)
    assert isinstance(explainer, expected_cls)


def test_similarity_explainer_limits_references_and_influence(monkeypatch):
    scores = {10: 0.2, 11: 0.5, 12: 0.9}
    store = _ScoringStore(scores)
    monkeypatch.setattr(
        "boardgames_api.domain.recommendations.explainers.get_boardgame",
        lambda bgg_id, db: _game(bgg_id),
    )
    context = RecommendationContext(
        liked_games=[10, 11, 12],
        play_context=PlayContextRequest(),
        num_results=1,
        candidates=[_game(99)],
        participant_id="p",
        study_group=StudyGroup.REFERENCES,
        embedding_index=store,
    )
    scored = [ScoredCandidate(candidate=_game(99), score=1.0)]
    explainer = SimilarityExplanationProvider(max_references=2)

    explanations = explainer.explain(context, scored, db=cast(Session, object()))
    refs = explanations[0].references or []
    assert [r.bgg_id for r in refs] == [12, 11]  # sorted by score desc, capped at 2
    assert [r.influence for r in refs] == ["positive", "neutral"]


def test_feature_explainer_positive_and_negative_hints(monkeypatch):
    store = _ScoringStore({1: 0.7})
    monkeypatch.setattr(
        "boardgames_api.domain.recommendations.explainers.get_boardgame",
        lambda bgg_id, db: _game(
            int(bgg_id),
            mechanics=["auction bidding"],
            themes=["space exploration"],
            genre=[],
        ),
    )
    context = RecommendationContext(
        liked_games=[1],
        play_context=PlayContextRequest(),
        num_results=1,
        candidates=[
            _game(
                5,
                mechanics=["auction bidding"],
                themes=["space exploration"],
                genre=["strategy"],
            )
        ],
        participant_id="p",
        study_group=StudyGroup.FEATURES,
        embedding_index=store,
    )
    scored = [ScoredCandidate(candidate=context.candidates[0], score=1.0)]
    explainer = FeatureHintExplanationProvider(max_features=3)

    explanations = explainer.explain(context, scored, db=cast(Session, object()))
    features = explanations[0].features or []
    assert [f.label for f in features] == ["auction bidding", "space exploration", "strategy"]
    assert [f.influence for f in features] == ["positive", "positive", "negative"]
