import logging
import os
import uuid
from datetime import datetime, timezone

from boardgames_api.domain.games.records import BoardgameRecord
from boardgames_api.domain.games.repository import BoardgameRepository
from boardgames_api.domain.participants.exceptions import ParticipantNotFoundError
from boardgames_api.domain.participants.records import StudyGroup
from boardgames_api.domain.participants.repository import ParticipantRepository
from boardgames_api.domain.recommendations.exceptions import (
    BoardgameMetadataMissing,
    RecommendationNotFoundError,
    RecommendationUnauthorizedError,
    RecommendationUnavailableError,
)
from boardgames_api.domain.recommendations.explainers import (
    Explainer,
    FeatureHintExplanationProvider,
    SimilarityExplanationProvider,
)
from boardgames_api.domain.recommendations.models import RecommendationResult
from boardgames_api.domain.recommendations.reccomender import (
    EmbeddingSimilarityRecommender,
    Recommender,
    ScoredGameId,
)
from boardgames_api.domain.recommendations.repository import RecommendationRepository
from boardgames_api.domain.recommendations.schemas import PlayContextRequest, RecommendationRequest
from boardgames_api.infrastructure.embeddings import load_embedding

RECOMMENDER_VERSION = os.getenv("BOARDGAMES_RECOMMENDER_VERSION", "v1")
logger = logging.getLogger(__name__)
PlayContext = PlayContextRequest


def _select_explainer(study_group: StudyGroup) -> Explainer:
    if study_group == StudyGroup.FEATURES:
        return FeatureHintExplanationProvider()
    if study_group == StudyGroup.REFERENCES:
        return SimilarityExplanationProvider()
    raise RecommendationUnavailableError(f"Unknown study group '{study_group}'")


def generate_recommendations(
    request: RecommendationRequest,
    participant_id: str,
    participant_repo: ParticipantRepository,
    recommendation_repo: RecommendationRepository,
    boardgame_repo: BoardgameRepository,
    recommender: Recommender = EmbeddingSimilarityRecommender(),
    study_group_override: StudyGroup | None = None,
) -> RecommendationResult:
    """
    Generate, explain, and persist a recommendation for a participant.

    Steps:
    - Resolve the participant (optionally overriding their study group).
    - Filter ranked ids by the play context.
    - Add explanations via the study-group-specific explainer.
    - Hydrate only the filtered winners and persist the domain RecommendationResult.

    Raises:
        ParticipantNotFoundError: if the participant_id cannot be loaded.
        RecommendationUnavailableError: if the study group is unknown or if ranking /
            explaining fails upstream.
    """
    participant = _resolve_participant(participant_repo, participant_id)
    study_group = study_group_override or participant.study_group
    # Choose explainer based on study group (features vs references)
    explainer = _select_explainer(study_group)

    logger.info(
        "generate_recommendations: participant=%s study_group=%s liked_games=%d requested=%d",
        participant_id,
        study_group.value,
        len(request.liked_games),
        request.num_results,
    )

    scored_candidates = _recommend_candidates(
        recommender=recommender,
        liked_game_ids=request.liked_games,
        requested=request.num_results,
    )
    filtered_scored = _filter_for_context(
        scored=scored_candidates,
        boardgame_repo=boardgame_repo,
        play_context=request.play_context,
        limit=request.num_results,
    )
    boardgames = _fetch_boardgames(scored=filtered_scored, boardgame_repo=boardgame_repo)

    explanations = explainer.add_explanations(
        ranked=filtered_scored,
        liked_games=request.liked_games,
        boardgames=boardgames,
    )

    result = RecommendationResult.from_ranked(
        request=request,
        participant_id=participant_id,
        study_group=study_group,
        ranked=filtered_scored,
        explanations=explanations,
        model_version=RECOMMENDER_VERSION,
        rec_id=f"rec-{uuid.uuid4().hex}",
        created_at=datetime.now(timezone.utc),
        boardgames=boardgames,
    )
    recommendation_repo.save(result)
    return result


def _resolve_participant(participant_repo: ParticipantRepository, participant_id: str):
    participant = participant_repo.get(participant_id)
    if participant is None:
        raise ParticipantNotFoundError("Participant not found.")
    return participant


def _recommend_candidates(
    recommender: Recommender,
    liked_game_ids: list[int],
    requested: int,
) -> list[ScoredGameId]:
    load_embedding()  # fail fast if embeddings are unavailable
    ranked: list[ScoredGameId] = recommender.recommend(
        liked_games=liked_game_ids,
        num_results=requested * 5,
    )
    if not ranked:
        raise RecommendationUnavailableError("No ranked candidates available.")
    return ranked


def _filter_for_context(
    scored: list[ScoredGameId],
    boardgame_repo: BoardgameRepository,
    play_context: PlayContext,
    limit: int,
) -> list[ScoredGameId]:
    ranked_ids = [item.bgg_id for item in scored]
    filtered_ids = boardgame_repo.filter_ids_for_context(
        play_context=play_context, candidate_ids=ranked_ids
    )
    ranked_by_id = {item.bgg_id: item for item in scored}
    filtered_ranked: list[ScoredGameId] = [
        ranked_by_id[rid] for rid in filtered_ids if rid in ranked_by_id
    ][:limit]
    if not filtered_ranked:
        raise RecommendationUnavailableError("No recommendations matched the play context.")
    return filtered_ranked


def _fetch_boardgames(
    scored: list[ScoredGameId],
    boardgame_repo: BoardgameRepository,
) -> list[BoardgameRecord]:
    ranked_records: list[BoardgameRecord] = boardgame_repo.get_many(
        [item.bgg_id for item in scored]
    )
    if len(ranked_records) != len(scored):
        missing = sorted({item.bgg_id for item in scored} - {bg.id for bg in ranked_records})
        raise BoardgameMetadataMissing(f"Missing boardgame metadata for ids: {missing}")
    return ranked_records


def get_recommendation(
    recommendation_id: str,
    participant_id: str,
    recommendation_repo: RecommendationRepository,
) -> RecommendationResult:
    rec = recommendation_repo.get(recommendation_id)
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
    return rec
