from pathlib import Path
from typing import Any, Dict
from urllib.parse import quote

import requests
import schemathesis
from boardgames_api.app import app
from fastapi.testclient import TestClient
from httpx import Response as HTTPXResponse
from requests.structures import CaseInsensitiveDict
from schemathesis.core import NotSet

# Load the OpenAPI schema from the provided YAML file
PROJECT_ROOT = Path(__file__).resolve().parents[2]
schema = schemathesis.openapi.from_path(PROJECT_ROOT / "openapi.yaml")

# Use FastAPI's TestClient to make requests
client = TestClient(app)


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
def test_api(case: Any) -> None:
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

    client.cookies.clear()
    cookies = _maybe(case.cookies)
    if isinstance(cookies, dict):
        cookies = {
            str(key): quote(str(value), safe="") for key, value in cookies.items()
        }
    if cookies:
        for key, value in cookies.items():
            client.cookies.set(key, value)

    response = client.request(**request_kwargs)
    case.validate_response(_httpx_to_requests(response))
