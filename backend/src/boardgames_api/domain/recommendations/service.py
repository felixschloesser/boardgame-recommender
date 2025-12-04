import datetime
import random
from typing import List

from sqlalchemy import select

from boardgames_api.domain.games.models import BoardgameRecord
from boardgames_api.domain.games.schemas import BoardGameResponse
from boardgames_api.domain.recommendations import repository as recommendations_repo
from boardgames_api.domain.recommendations.exceptions import (
    RecommendationInputError,
    RecommendationNotFoundError,
    RecommendationUnavailableError,
)
from boardgames_api.domain.recommendations.schemas import (
    Recommendation,
    RecommendationExplanation,
    RecommendationRequest,
    ReferenceExplanation,
    Selection,
)
from boardgames_api.persistence.database import ensure_seeded, get_session
from boardgames_api.utils.embedding import get_embedding_store


def _record_to_boardgame(record: BoardgameRecord) -> BoardGameResponse:
    complexity = record.complexity or 0
    if complexity < 0:
        complexity = 0

    age = int(record.age_recommendation or 0)
    if age < 0:
        age = 0

    min_players = max(1, record.min_players)
    max_players = max(min_players, record.max_players)
    playing_time = max(1, record.playing_time_minutes)

    return BoardGameResponse(
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


def _load_boardgames() -> List[BoardGameResponse]:
    ensure_seeded()
    with get_session() as session:
        records = session.scalars(select(BoardgameRecord)).all()
    return [_record_to_boardgame(record) for record in records] if records else []


def generate_recommendations(request: RecommendationRequest) -> Recommendation:
    """
    Generate recommendations based on the participant's preferences.
    Uses the trained embedding vectors when available; falls back to random sampling otherwise.
    """
    available_games = _load_boardgames()
    if not available_games:
        raise RecommendationUnavailableError("The recommender system is currently unavailable.")

    desired_results = request.num_results

    filtered_games = []
    for game in available_games:
        if (
            request.play_context
            and request.play_context.players
            and not (game.min_players <= request.play_context.players <= game.max_players)
        ):
            continue

        if request.play_context and request.play_context.duration:
            max_minutes = {
                "short": 45,
                "medium": 90,
                "long": 240,
            }.get(request.play_context.duration.value)
            if max_minutes is None:
                max_minutes = 240
            if game.playing_time_minutes > max_minutes:
                continue

        filtered_games.append(game)

    if not filtered_games:
        context_parts: list[str] = []
        if request.play_context and request.play_context.players:
            context_parts.append(f"player count {request.play_context.players}")
        if request.play_context and request.play_context.duration:
            context_parts.append(f"duration '{request.play_context.duration.value}'")
        context_msg = f" for {', '.join(context_parts)}" if context_parts else ""
        raise RecommendationInputError(
            f"No recommendations could be generated{context_msg}. "
            "Try adjusting player count, duration, or liked games."
        )

    store = get_embedding_store()
    if store is None:
        raise RecommendationUnavailableError(
            (
                "Embedding store is not available; "
                "train and load embeddings before requesting recommendations."
            )
        )
    response_recommendations: list[Selection] = []

    missing_liked = [int(liked) for liked in request.liked_games if not store.has_id(int(liked))]
    liked_ids = [int(liked) for liked in request.liked_games if store.has_id(int(liked))]
    if missing_liked:
        missing_str = ", ".join(str(g) for g in missing_liked)
        raise RecommendationInputError(
            f"Liked games not found in embeddings: {missing_str}. "
            "Choose liked games that exist in the dataset."
        )

    candidate_ids = [int(game.id) for game in filtered_games if store.has_id(int(game.id))]
    if not candidate_ids:
        raise RecommendationUnavailableError(
            (
                "No candidate games with embeddings matched the filters; "
                "try adjusting constraints or regenerating embeddings."
            )
        )

    scores = store.score_candidates(liked_ids, candidate_ids)

    if not scores:
        raise RecommendationUnavailableError(
            "Unable to score candidates with the current embeddings; retrain or adjust inputs."
        )

    filtered_by_id = {int(game.id): game for game in filtered_games}
    ranked_ids = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    for game_id, score in ranked_ids[:desired_results]:
        game = filtered_by_id.get(int(game_id))
        if not game:
            continue
        references = [
            ReferenceExplanation(
                bgg_id=liked,
                title=store.get_name(liked) or "",
                influence="positive",
            )
            for liked in liked_ids[:3]
        ]
        explanation = RecommendationExplanation(
            type="references",
            references=references,
        )
        response_recommendations.append(
            Selection(
                boardgame=game,
                explanation=explanation,
            )
        )

    rec_id = f"rec_{random.randint(1000, 9999)}"
    participant_id = f"participant_{random.randint(1000, 9999)}"

    recommendation = Recommendation(
        id=rec_id,
        participant_id=participant_id,
        created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        intent=request,
        model_version=(store.run_identifier if store else "v1"),
        experiment_group="default",
        recommendations=response_recommendations[:desired_results],
    )

    recommendations_repo.save_recommendation(recommendation)
    return recommendation


def get_recommendation_snapshot(recommendation_id: str) -> Recommendation:
    """
    Retrieve a stored recommendation by its identifier.
    """
    rec = recommendations_repo.get_recommendation(recommendation_id)
    if not rec:
        raise RecommendationNotFoundError("Recommendation not found.")
    return rec
