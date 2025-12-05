import logging
import os
import uuid
from datetime import datetime, timezone
from typing import List

from sqlalchemy.orm import Session

from boardgames_api.domain.games.records import BoardgameRecord
from boardgames_api.domain.games.repository import BoardgameRepository
from boardgames_api.domain.games.schemas import BoardGameResponse
from boardgames_api.domain.participants.records import StudyGroup
from boardgames_api.domain.recommendations.context import RecommendationContext
from boardgames_api.domain.recommendations.exceptions import (
    RecommendationInputError,
    RecommendationNotFoundError,
    RecommendationUnauthorizedError,
    RecommendationUnavailableError,
)
from boardgames_api.domain.recommendations.explainers import (
    FeatureHintExplanationProvider,
    SimilarityExplanationProvider,
)
from boardgames_api.domain.recommendations.models import (
    RecommendationResult,
    RecommendationSelection,
)
from boardgames_api.domain.recommendations.pipeline import Explainer, run_pipeline
from boardgames_api.domain.recommendations.repository import RecommendationRepository
from boardgames_api.domain.recommendations.schemas import (
    PlayContextRequest,
    Recommendation,
    RecommendationRequest,
)
from boardgames_api.domain.recommendations.scoring import EmbeddingScorer
from boardgames_api.utils.embedding import get_embedding_index

RECOMMENDER_VERSION = os.getenv("BOARDGAMES_RECOMMENDER_VERSION", "v1")
DEFAULT_SCORER = EmbeddingScorer()
logger = logging.getLogger(__name__)


def _select_explainer(study_group: StudyGroup) -> Explainer:
    """
    Map study group to explanation provider. Scoring remains the same.
    """
    if study_group == StudyGroup.FEATURES:
        return FeatureHintExplanationProvider()
    if study_group == StudyGroup.REFERENCES:
        return SimilarityExplanationProvider()
    raise RecommendationUnavailableError(
        f"Unknown study group '{study_group.value}' for explainer selection."
    )

def _fetch_candidates(
    play_context: PlayContextRequest, desired_results: int, db: Session
) -> List[BoardGameResponse]:
    """
    Fetch a limited set of candidate games filtered by play context.
    """
    players = play_context.players
    duration = play_context.duration
    max_minutes = None
    if duration is not None:
        max_minutes = {
            "short": 45,
            "medium": 90,
            "long": 240,
        }.get(getattr(duration, "value", duration))
    limit = max(200, desired_results * 50)
    repo = BoardgameRepository(db)
    records = repo.list_for_play_context(
        players=players,
        max_minutes=max_minutes,
        limit=limit,
    )
    return [BoardGameResponse.from_record(record) for record in records]


def generate_recommendations(
    request: RecommendationRequest,
    participant_id: str,
    study_group: StudyGroup,
    db: Session,
    scorer: EmbeddingScorer = DEFAULT_SCORER,
) -> Recommendation:
    """
    Generate recommendations based on the participant's preferences using the embedding store.
    """
    logger.info(
        "generate_recommendations: participant=%s study_group=%s liked_games=%d requested=%d",
        participant_id,
        study_group.value,
        len(request.liked_games),
        request.num_results,
    )

    play_context = request.play_context or PlayContextRequest()
    candidates = _fetch_candidates(play_context, request.num_results, db)
    if not candidates:
        context_parts: list[str] = []
        if play_context.players:
            context_parts.append(f"player count {play_context.players}")
        if play_context.duration:
            context_parts.append(f"duration '{play_context.duration.value}'")
        context_msg = f" for {', '.join(context_parts)}" if context_parts else ""
        raise RecommendationInputError(
            f"No recommendations could be generated{context_msg}. "
            "Try adjusting player count, duration, or liked games."
        )

    store = get_embedding_index()
    if store is None:
        raise RecommendationUnavailableError(
            "Embedding store is not available; train and load embeddings before "
            "requesting recommendations."
        )

    missing_liked = [int(liked) for liked in request.liked_games if not store.has_id(int(liked))]
    if missing_liked:
        missing_str = ", ".join(str(g) for g in missing_liked)
        raise RecommendationInputError(
            f"Liked games not found in embeddings: {missing_str}. "
            "Choose liked games that exist in the dataset."
        )

    context = RecommendationContext(
        liked_games=list(request.liked_games),
        play_context=play_context,
        num_results=request.num_results,
        candidates=candidates,
        participant_id=participant_id,
        study_group=study_group,
        embedding_index=store,
    )

    explainer = _select_explainer(study_group)
    selections = run_pipeline(context=context, scorer=scorer, explainer=explainer)

    rec_id = f"rec-{uuid.uuid4().hex}"
    result = RecommendationResult(
        id=rec_id,
        participant_id=participant_id,
        created_at=datetime.now(timezone.utc),
        intent=request,
        model_version=RECOMMENDER_VERSION,
        experiment_group=study_group,
        selections=[
            RecommendationSelection(
                boardgame=BoardgameRecord(
                    id=int(sel.boardgame.id),
                    title=sel.boardgame.title,
                    description=sel.boardgame.description,
                    mechanics=sel.boardgame.mechanics,
                    genre=sel.boardgame.genre,
                    themes=sel.boardgame.themes,
                    min_players=sel.boardgame.min_players,
                    max_players=sel.boardgame.max_players,
                    complexity=sel.boardgame.complexity,
                    age_recommendation=sel.boardgame.age_recommendation,
                    num_user_ratings=sel.boardgame.num_user_ratings,
                    avg_user_rating=sel.boardgame.avg_user_rating,
                    year_published=sel.boardgame.year_published,
                    playing_time_minutes=sel.boardgame.playing_time_minutes,
                    image_url=sel.boardgame.image_url,
                    bgg_url=sel.boardgame.bgg_url,
                ),
                explanation=sel.explanation,
            )
            for sel in selections[: request.num_results]
        ],
    )

    RecommendationRepository(db).save(result)
    logger.info(
        "recommendation_generated: rec_id=%s participant=%s study_group=%s selections=%d",
        rec_id,
        participant_id,
        study_group.value,
        len(result.selections),
    )
    return Recommendation.from_domain(result)


def get_recommendation(
    recommendation_id: str,
    participant_id: str,
    db: Session,
) -> Recommendation:
    """
    Retrieve a stored recommendation by its identifier.
    """
    rec = RecommendationRepository(db).get(recommendation_id)
    if not rec:
        raise RecommendationNotFoundError("Recommendation not found.")
    if rec.participant_id != participant_id:
        logger.warning(
            "recommendation_access_denied: rec_id=%s requester=%s owner=%s",
            recommendation_id,
            participant_id,
            rec.participant_id,
        )
        raise RecommendationUnauthorizedError("Recommendation belongs to a different participant.")
    return Recommendation.from_domain(rec)
