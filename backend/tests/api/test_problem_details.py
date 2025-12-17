from typing import Iterable


def _assert_problem_details(
    body: dict,
    status: int,
    title: str,
    type_: str = "about:blank",
    require_invalid_params: bool = False,
    expected_param_names: Iterable[str] = (),
) -> None:
    assert body.get("type") == type_
    assert body.get("title") == title
    assert body.get("status") == status
    if require_invalid_params:
        params = body.get("invalid_params")
        assert isinstance(params, list)
        names = [item.get("name") for item in params]
        for name in expected_param_names:
            assert name in names
        for item in params:
            assert set(item.keys()) == {"name", "reason"} or set(item.keys()) == {
                "name",
                "reason",
                "code",
            }
    else:
        assert "invalid_params" not in body or body.get("invalid_params") is None


def test_recommendations_validation_errors_return_rfc7807_problem_details(client) -> None:
    participant_resp = client.post("/api/auth/participant", json={})
    assert participant_resp.status_code == 201
    pid = participant_resp.json().get("participant_id")
    session_resp = client.post("/api/auth/session", json={"participant_id": pid})
    assert session_resp.status_code == 200
    payload = {
        "liked_games": [0],
        "num_results": 10,
    }
    response = client.post("/api/recommendation", json=payload, cookies=session_resp.cookies)

    assert response.status_code == 400
    assert response.headers.get("content-type", "").startswith("application/problem+json")
    body = response.json()
    _assert_problem_details(
        body,
        status=400,
        title="Bad Request",
        type_="https://boardgames.app/problems/validation-error",
        require_invalid_params=True,
        expected_param_names=("liked_games[0]",),
    )
    reasons = " ".join(item["reason"] for item in body["invalid_params"])
    assert "positive integers" in reasons or "at least one" in reasons


def test_not_found_returns_rfc7807_problem_details(client) -> None:
    response = client.get("/api/games/9999999")

    assert response.status_code == 404
    assert response.headers.get("content-type", "").startswith("application/problem+json")
    body = response.json()
    _assert_problem_details(
        body,
        status=404,
        title="Not Found",
        type_="https://boardgames.app/problems/not-found",
    )
    assert body.get("detail")


def test_unauthorized_returns_rfc7807_problem_details(client) -> None:
    client.cookies.clear()
    response = client.delete("/api/auth/session")

    assert response.status_code == 401
    assert response.headers.get("content-type", "").startswith("application/problem+json")
    body = response.json()
    _assert_problem_details(
        body,
        status=401,
        title="Unauthorized",
        type_="https://boardgames.app/problems/unauthorized",
    )
    assert body.get("detail")
