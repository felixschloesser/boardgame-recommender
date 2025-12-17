from __future__ import annotations

import numpy as np
import pytest
from boardgames_api.domain.participants.records import StudyGroup
from boardgames_api.domain.recommendations.explainers import (
    FeatureHintExplanationProvider,
    SimilarityExplanationProvider,
)
from boardgames_api.domain.recommendations.reccomender import ScoredGameId
from boardgames_api.domain.recommendations.schemas import RecommendationExplanation
from boardgames_api.domain.recommendations.service import _select_explainer
from boardgames_api.infrastructure.embeddings import Embeddings


class _Game:
    def __init__(self, id: int, mechanics=None, themes=None, genre=None, title: str = "Game"):
        self.id = id
        self.mechanics = mechanics or []
        self.themes = themes or []
        self.genre = genre or []
        self.title = title


def _store(names: dict[int, str]) -> Embeddings:
    ids = list(names.keys()) or [1]
    vecs = np.eye(len(ids))
    norms = np.linalg.norm(vecs, axis=1)
    return Embeddings(
        run_identifier="test",
        bgg_ids=np.array(ids),
        vectors=vecs,
        norms=norms,
        names=names,
    )


def test_similarity_explainer_uses_liked_refs(monkeypatch):
    store = _store({10: "Alpha", 11: "Beta"})
    monkeypatch.setattr(
        "boardgames_api.domain.recommendations.explainers.load_embedding", lambda: store
    )
    explainer = SimilarityExplanationProvider(max_references=2)
    ranked = [ScoredGameId(bgg_id=2, score=0.9)]

    explanations = explainer.add_explanations(ranked=ranked, liked_games=[10, 11], boardgames=[])
    assert len(explanations) == 1
    refs = explanations[0].references or []
    assert [r.bgg_id for r in refs] == [10, 11]
    assert [r.title for r in refs] == ["Alpha", "Beta"]


def test_feature_explainer_prioritizes_mechanics_then_themes_then_genre():
    game = _Game(
        id=5,
        mechanics=["Deck Building"],
        themes=["Space"],
        genre=["Strategy"],
        title="Galactic Decks",
    )
    ranked = [ScoredGameId(bgg_id=5, score=1.0)]
    explainer = FeatureHintExplanationProvider(max_features=3)

    explanations = explainer.add_explanations(ranked=ranked, liked_games=[], boardgames=[game])
    features = explanations[0].features or []
    assert [f.label for f in features] == ["Deck Building", "Space", "Strategy"]
    assert all(f.influence == "positive" for f in features)


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


def test_feature_explainer_handles_missing_boardgame():
    ranked = [ScoredGameId(bgg_id=1, score=1.0)]
    explainer = FeatureHintExplanationProvider()
    explanations = explainer.add_explanations(ranked=ranked, liked_games=[], boardgames=[])
    # Without metadata, expect an explanation entry with no features.
    assert isinstance(explanations[0], RecommendationExplanation)
    assert explanations[0].features == []
