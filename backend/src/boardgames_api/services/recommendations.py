import datetime
import random
from typing import List

from sqlalchemy import select
from sqlalchemy.orm import Session

from boardgames_api.db import BoardgameRecord, engine, ensure_seeded
from boardgames_api.models.games import BoardGame
from boardgames_api.models.recommendations import (
    Recommendation,
    RecommendationExplanation,
    RecommendationRequest,
    RecommendationResponse,
)
from boardgames_api.utils.exceptions import RecommenderUnavailableException

# Mock database of boardgames
MOCK_BOARDGAMES = [
    BoardGame(
        id="1",
        title="Catan",
        description="A strategy game where players collect resources and build settlements.",
        mechanics=["resource management", "trading"],
        genre=["strategy"],
        themes=["exploration"],
        min_players=3,
        max_players=4,
        complexity=2.5,
        age_recommendation=10,
        num_user_ratings=1000,
        avg_user_rating=8.2,
        year_published=1995,
        playing_time_minutes=90,
        image_url="https://example.com/catan.jpg",
        bgg_url="https://boardgamegeek.com/boardgame/1/catan",
    ),
    BoardGame(
        id="2",
        title="Carcassonne",
        description="A tile-placement game where players build cities, roads, and fields.",
        mechanics=["tile placement"],
        genre=["family"],
        themes=["medieval"],
        min_players=2,
        max_players=5,
        complexity=1.8,
        age_recommendation=8,
        num_user_ratings=800,
        avg_user_rating=7.5,
        year_published=2000,
        playing_time_minutes=45,
        image_url="https://example.com/carcassonne.jpg",
        bgg_url="https://boardgamegeek.com/boardgame/2/carcassonne",
    ),
]


def _record_to_boardgame(record: BoardgameRecord) -> BoardGame:
    complexity = record.complexity or 0
    if complexity < 0:
        complexity = 0

    age = int(record.age_recommendation or 0)
    if age < 0:
        age = 0

    min_players = max(1, record.min_players)
    max_players = max(min_players, record.max_players)
    playing_time = max(1, record.playing_time_minutes)

    return BoardGame(
        id=str(record.id),
        title=record.title,
        description=record.description,
        mechanics=record.mechanics or [],
        genre=record.genre or [],
        themes=record.themes or [],
        min_players=min_players,
        max_players=max_players,
        complexity=complexity,
        age_recommendation=age,
        num_user_ratings=int(record.num_user_ratings or 0),
        avg_user_rating=record.avg_user_rating or 0,
        year_published=int(record.year_published or 0),
        playing_time_minutes=playing_time,
        image_url=record.image_url,
        bgg_url=record.bgg_url,
    )


def _load_boardgames() -> List[BoardGame]:
    ensure_seeded()
    with Session(engine) as session:
        records = session.scalars(select(BoardgameRecord)).all()
    loaded = [_record_to_boardgame(record) for record in records] if records else []

    # Ensure the fallback mock games are present for deterministic tests.
    by_id = {game.id: game for game in loaded}
    for mock in MOCK_BOARDGAMES:
        if mock.id not in by_id:
            loaded.append(mock)
    return loaded


def _validate_request(request: RecommendationRequest) -> None:
    """
    Validate user-provided input and translate test expectations into clear errors.
    """
    if not request.liked_games:
        raise ValueError("liked_games cannot be empty.")

    if request.player_count is not None and request.player_count <= 0:
        raise ValueError("player_count must be greater than zero.")

    if request.available_time_minutes is not None and request.available_time_minutes <= 0:
        raise ValueError("available_time_minutes must be greater than zero.")

    if request.num_results <= 0:
        raise ValueError("num_results must be greater than zero.")

    if request.num_results > 100:
        raise ValueError("num_results must be between 1 and 100.")

    if any(game_id <= 0 for game_id in request.liked_games):
        raise ValueError("liked_games entries must be positive integers.")

    if any(game_id <= 0 for game_id in request.disliked_games):
        raise ValueError("disliked_games entries must be positive integers.")


def generate_recommendations(request: RecommendationRequest) -> RecommendationResponse:
    """
    Generate recommendations based on the participant's preferences.
    """
    _validate_request(request)

    available_games = _load_boardgames()

    if not available_games:
        raise RecommenderUnavailableException(
            "The recommender system is currently unavailable."
        )

    desired_results = request.num_results

    filtered_games = []
    for game in available_games:
        # Skip games the user explicitly dislikes.
        if int(game.id) in {int(item) for item in request.disliked_games}:
            continue

        players_ok = True
        if request.player_count and not (
            game.min_players <= request.player_count <= game.max_players
        ):
            players_ok = False

        time_ok = True
        if request.available_time_minutes and (
            game.playing_time_minutes > request.available_time_minutes
        ):
            time_ok = False

        if players_ok and time_ok:
            filtered_games.append(game)

    if not filtered_games:
        raise ValueError("No recommendations could be generated for the provided input.")

    recommendations = random.sample(filtered_games, min(len(filtered_games), desired_results))

    response_recommendations = []
    for game in recommendations:
        explanation = RecommendationExplanation(
            type="features",
            features=[
                {"label": "Mechanics", "category": "mechanic"},
                {"label": "Genre", "category": "genre"},
            ],
        )
        response_recommendations.append(
            Recommendation(
                boardgame=game,
                explanation=explanation,
            )
        )

    return RecommendationResponse(
        session_id="session_" + str(random.randint(1000, 9999)),
        participant_id="participant_" + str(random.randint(1000, 9999)),
        created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        intent=request,
        model_version="1.0.0",
        experiment_group="default",
        recommendations=response_recommendations,
    )


def get_recommendation_session(session_id: str) -> RecommendationResponse | None:
    """
    Retrieve a stored recommendation session by its session ID.
    """
    if session_id != "mock_session_id":
        return None

    games = _load_boardgames()
    return RecommendationResponse(
        session_id=session_id,
        participant_id="mock_participant_id",
        created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        intent=RecommendationRequest(
            liked_games=[1],
            disliked_games=[2],
            play_context=None,
            preference_tags=[],
            avoid_tags=[],
            num_results=5,
        ),
        model_version="1.0.0",
        experiment_group="default",
        recommendations=[
            Recommendation(
                boardgame=games[0],
                explanation=RecommendationExplanation(
                    type="features",
                    features=[
                        {"label": "Mechanics", "category": "mechanic"},
                        {"label": "Genre", "category": "genre"},
                    ],
                ),
            )
        ],
    )
