from __future__ import annotations

from boardgames_api.app import app
from boardgames_api.domain.recommendations.schemas import (
    RecommendationRequest,
    RecommendationResponse,
)


def test_openapi_examples_validate_against_schemas() -> None:
    schema = app.openapi()
    path = schema["paths"]["/api/recommendation"]["post"]
    request_examples = (
        path.get("requestBody", {})
        .get("content", {})
        .get("application/json", {})
        .get("examples", {})
    )
    for example in request_examples.values():
        payload = example.get("value")
        RecommendationRequest.model_validate(payload)

    response_examples = (
        path.get("responses", {})
        .get("201", {})
        .get("content", {})
        .get("application/json", {})
        .get("examples", {})
    )
    for example in response_examples.values():
        payload = example.get("value")
        RecommendationResponse.model_validate(payload)
