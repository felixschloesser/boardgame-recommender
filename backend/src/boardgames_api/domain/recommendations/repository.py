from typing import Any, Mapping, Optional, cast

from sqlalchemy.orm import Session

from boardgames_api.domain.recommendations.models import RecommendationRecord
from boardgames_api.domain.recommendations.schemas import Recommendation
from boardgames_api.persistence.database import get_engine, init_db


def save_recommendation(entity: Recommendation) -> None:
    """
    Persist a recommendation payload.
    """
    engine = get_engine()
    init_db()
    with Session(engine) as db:
        record = RecommendationRecord(
            id=entity.id,
            participant_id=entity.participant_id,
            created_at=entity.created_at,
            model_version=entity.model_version,
            experiment_group=entity.experiment_group,
            intent=entity.intent.model_dump(mode="json"),
            recommendations=[
                selection.model_dump(mode="json") for selection in entity.recommendations
            ],
        )
        db.merge(record)
        db.commit()


def get_recommendation(recommendation_id: str) -> Optional[Recommendation]:
    """
    Retrieve a persisted recommendation.
    """
    engine = get_engine()
    init_db()
    with Session(engine) as db:
        record = db.get(RecommendationRecord, recommendation_id)
        if not record:
            return None
        intent_payload = dict(record.intent or {})
        for key in (
            "available_time_minutes",
            "player_count",
            "disliked_games",
            "preference_tags",
            "avoid_tags",
        ):
            intent_payload.pop(key, None)
        recs_payload: list[dict[str, object]] = []
        for rec_obj in record.recommendations or []:
            if not isinstance(rec_obj, Mapping):
                continue
            rec_dict: dict[str, object] = dict(rec_obj)
            explanation_raw = rec_dict.get("explanation")
            explanation: dict[str, object] = (
                dict(cast(Mapping[str, object], explanation_raw))
                if isinstance(explanation_raw, Mapping)
                else {}
            )
            if explanation.get("type") == "features":
                features_raw = explanation.get("features")
                features_list: list[Mapping[str, Any]] = (
                    [cast(Mapping[str, Any], f) for f in features_raw if isinstance(f, Mapping)]
                    if isinstance(features_raw, list)
                    else []
                )
                explanation["features"] = [
                    {
                        "label": str(f.get("label", "")),
                        "category": str(f.get("category", "mechanic")),
                        "influence": str(f.get("influence", "positive")),
                    }
                    for f in features_list
                ]
            if explanation.get("type") == "references":
                references_raw = explanation.get("references")
                references_list: list[Mapping[str, Any]] = (
                    [cast(Mapping[str, Any], r) for r in references_raw if isinstance(r, Mapping)]
                    if isinstance(references_raw, list)
                    else []
                )
                explanation["references"] = [
                    {
                        "bgg_id": int(ref.get("bgg_id", 0)),
                        "title": str(ref.get("title", "")),
                        "influence": str(ref.get("influence", "positive")),
                    }
                    for ref in references_list
                ]
            rec_dict["explanation"] = explanation
            recs_payload.append(rec_dict)
        data = {
            "id": record.id,
            "participant_id": record.participant_id,
            "created_at": record.created_at,
            "intent": intent_payload,
            "model_version": record.model_version,
            "experiment_group": record.experiment_group,
            "recommendations": recs_payload,
        }
        return Recommendation.model_validate(data)
