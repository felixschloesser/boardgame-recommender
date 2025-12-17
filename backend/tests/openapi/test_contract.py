from pathlib import Path
from typing import Any, Dict
from urllib.parse import quote

import requests
import schemathesis
from httpx import Response as HTTPXResponse
from hypothesis import HealthCheck, settings
from requests.structures import CaseInsensitiveDict
from schemathesis.core import NotSet

# Load the OpenAPI schema from the provided YAML file
PROJECT_ROOT = Path(__file__).resolve().parents[3]
schema = schemathesis.openapi.from_path(PROJECT_ROOT / "openapi.yaml")


def _setup_auth(client) -> dict[str, str]:
    """Create participant + session for fuzzing authenticated endpoints."""
    p_resp = client.post("/api/auth/participant", json={})
    assert p_resp.status_code == 201
    pid = p_resp.json().get("participant_id")
    s_resp = client.post("/api/auth/session", json={"participant_id": pid})
    assert s_resp.status_code == 200
    return {str(cookie.name): str(cookie.value or "") for cookie in s_resp.cookies.jar}


class _RawAdapter:
    def __init__(self, headers: dict[str, str]):
        self.headers = headers
        self.version = 11


class _HeadersAdapter(dict[str, str]):
    def getlist(self, name: str) -> list[str]:
        value = self.get(name)
        if value is None:
            return []
        if isinstance(value, list):
            return value
        return [value]


def _httpx_to_requests(response: HTTPXResponse) -> requests.Response:
    try:
        request_content = response.request.content
    except Exception:
        request_content = b""

    prepared_request = requests.Request(
        method=response.request.method,
        url=str(response.request.url),
        headers=dict(response.request.headers),
        data=request_content,
    ).prepare()

    raw_headers = _HeadersAdapter(dict(response.headers))
    adapted = requests.Response()
    adapted.status_code = response.status_code
    adapted._content = response.content
    adapted.headers = CaseInsensitiveDict(response.headers)
    adapted.url = str(response.url)
    adapted.reason = response.reason_phrase
    adapted.encoding = response.encoding
    adapted.request = prepared_request
    adapted.raw = _RawAdapter(raw_headers)
    return adapted


def _maybe(value: Any) -> Any | None:
    return None if isinstance(value, NotSet) else value


@schema.parametrize()
@settings(
    max_examples=10,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
)
def test_api(case: Any, client) -> None:
    """
    Contract test to ensure the API implementation adheres to the OpenAPI spec.
    """
    path = "/api" + case.formatted_path

    request_kwargs: Dict[str, Any] = {
        "method": case.method,
        "url": path,
        "headers": _maybe(case.headers),
        "params": _maybe(case.query),
    }

    body = _maybe(case.body)
    if body is not None:
        request_kwargs["json"] = body

    files = getattr(case, "files", None)
    if files:
        request_kwargs["files"] = files
    # If this is a GET with no params but a body example, avoid sending JSON.
    if case.method.upper() == "GET" and "json" in request_kwargs and not request_kwargs["json"]:
        request_kwargs.pop("json", None)

    client.cookies.clear()
    cookies = _maybe(case.cookies)
    if isinstance(cookies, dict):
        cookies = {str(key): quote(str(value), safe="") for key, value in cookies.items()}
    if cookies:
        for key, value in cookies.items():
            client.cookies.set(key, value)
    else:
        # If the endpoint requires auth (has sessionCookie security), set it up.
        try:
            securities = case.security or []
        except AttributeError:
            securities = []
        for security in securities:
            if security and "sessionCookie" in security:
                for key, value in _setup_auth(client).items():
                    client.cookies.set(key, value)
                break

    response = client.request(**request_kwargs)
    case.validate_response(_httpx_to_requests(response))
