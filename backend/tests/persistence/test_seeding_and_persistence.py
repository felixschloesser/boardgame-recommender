from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import polars as pl
import pytest
from boardgames_api.domain.games.records import BoardgameRecord
from boardgames_api.domain.participants.records import StudyGroup
from boardgames_api.domain.recommendations.models import (
    RecommendationResult,
    RecommendationSelection,
)
from boardgames_api.domain.recommendations.repository import RecommendationRepository
from boardgames_api.domain.recommendations.schemas import (
    FeatureExplanation,
    RecommendationExplanation,
    RecommendationRequest,
    ReferenceExplanation,
)
from boardgames_api.infrastructure import database
from sqlalchemy import func, select


@pytest.fixture()
def temp_db(monkeypatch, tmp_path: Path):
    """
    Isolate the database for tests that manipulate seeding/persistence.
    """
    db_path = tmp_path / "app.sqlite3"
    monkeypatch.setenv("BOARDGAMES_DB_PATH", str(db_path))
    # Reset engine for this test run and restore afterwards.
    original_engine = database._engine
    original_default = database.DEFAULT_DB_PATH
    monkeypatch.setattr(database, "DEFAULT_DB_PATH", db_path, raising=False)
    monkeypatch.setattr(database, "_engine", None, raising=False)
    monkeypatch.setattr(database, "SessionLocal", None, raising=False)
    database.init_db()
    yield db_path
    database._engine = original_engine
    database.DEFAULT_DB_PATH = original_default


def test_seed_skips_invalid_rows(monkeypatch, tmp_path: Path, temp_db: Path) -> None:
    """
    seed_boardgames_from_parquet should ignore rows that violate schema bounds.
    """
    valid = {
        "bgg_id": [101],
        "name": ["Sample Seed"],
        "text_description": ["Clean description"],
        "cat_mechanics": [["deckbuilding"]],
        "cat_categories": [["strategy"]],
        "cat_themes": [["fantasy"]],
        "min_players": [2],
        "max_players": [4],
        "num_complexity": [2.5],
        "num_age_recommendation": [10],
        "num_num_user_ratings": [100],
        "avg_rating": [7.2],
        "num_year_published": [2020],
        "playing_time_minutes": [45],
    }
    invalid = {
        "bgg_id": [202],
        "name": ["Broken"],
        "text_description": ["Bad data"],
        "cat_mechanics": [["luck"]],
        "cat_categories": [["family"]],
        "cat_themes": [["none"]],
        "min_players": [0],  # invalid
        "max_players": [4],
        "num_complexity": [-1.0],  # invalid
        "num_age_recommendation": [-5],
        "num_num_user_ratings": [10],
        "avg_rating": [5.0],
        "num_year_published": [2010],
        "playing_time_minutes": [30],
    }
    df = pl.DataFrame(valid).vstack(pl.DataFrame(invalid))
    parquet_path = tmp_path / "seed.parquet"
    df.write_parquet(parquet_path)

    # Re-seed with the temporary DB
    database.seed_boardgames_from_parquet(parquet_path=parquet_path)
    with database.session_scope() as session:
        total = session.scalar(select(func.count(BoardgameRecord.id)))
        min_complexity = session.scalar(select(func.min(BoardgameRecord.complexity)))
        min_age = session.scalar(select(func.min(BoardgameRecord.age_recommendation)))
        min_min_players = session.scalar(select(func.min(BoardgameRecord.min_players)))

    assert total == 1
    assert min_complexity is None or min_complexity >= 0
    assert min_age is None or min_age >= 0
    assert min_min_players is None or min_min_players >= 1
    with database.get_session() as session:
        assert not database._boardgames_invalid(session)


def test_seed_no_parquet_is_noop(monkeypatch, tmp_path: Path, temp_db: Path) -> None:
    """
    When the parquet file is missing, seeding should be a no-op (return 0 rows).
    """
    missing = tmp_path / "does-not-exist.parquet"
    loaded = database.seed_boardgames_from_parquet(parquet_path=missing)
    assert loaded == 0


def test_recommendation_round_trip_persists_explanations(temp_db: Path) -> None:
    """
    Persisting and reloading a recommendation should preserve explanations and influence.
    """
    now = datetime.now(timezone.utc)
    recommendation = RecommendationResult(
        id="rec-1",
        participant_id="p-1",
        created_at=now,
        intent=RecommendationRequest.model_validate(
            {"liked_games": [1], "num_results": 1, "play_context": {"players": 2}}
        ),
        model_version="vX",
        experiment_group=StudyGroup.FEATURES,
        selections=[
            RecommendationSelection(
                boardgame=BoardgameRecord(
                    id=10,
                    title="Dominion",
                    description="Deckbuilder",
                    mechanics=["Deck Building"],
                    genre=["Strategy"],
                    themes=["Medieval"],
                    min_players=2,
                    max_players=4,
                    complexity=2.3,
                    age_recommendation=13,
                    num_user_ratings=120000,
                    avg_user_rating=7.5,
                    year_published=2008,
                    playing_time_minutes=30,
                    image_url="http://example.com",
                    bgg_url="http://example.com",
                ),
                explanation=RecommendationExplanation(
                    type="features",
                    features=[
                        FeatureExplanation(
                            label="Deck-building",
                            category="mechanic",
                            influence="positive",
                        )
                    ],
                    references=[
                        ReferenceExplanation(
                            bgg_id=1,
                            title="Catan",
                            influence="neutral",
                        )
                    ],
                ),
            )
        ],
    )
    from boardgames_api.infrastructure.database import session_scope

    with session_scope() as session:
        repo = RecommendationRepository(session)
        repo.save(recommendation)
        reloaded = repo.get("rec-1")
    assert reloaded is not None
    assert reloaded.intent.liked_games == [1]
    selection = reloaded.selections[0]
    assert selection.explanation.references and selection.explanation.references[0].bgg_id == 1
    assert (
        selection.explanation.features and selection.explanation.features[0].influence == "positive"
    )
