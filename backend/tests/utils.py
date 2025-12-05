from __future__ import annotations

from typing import Any


def assert_problem_details(body: dict[str, Any], *, status: int) -> None:
    assert body.get("status") == status
    assert "title" in body
    # type may be absent when using default ProblemDetailsResponse
    assert "type" in body or body.get("type") is None
