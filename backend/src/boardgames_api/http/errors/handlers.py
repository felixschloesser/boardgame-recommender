from http import HTTPStatus
from typing import Any, Mapping, Sequence

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette import status as starlette_status
from starlette.exceptions import HTTPException as StarletteHTTPException

from boardgames_api.domain.participants.exceptions import InvalidStudyTokenError
from boardgames_api.http.errors.schemas import (
    BadRequestResponse,
    NotFoundResponse,
    ProblemDetailsResponse,
    UnauthorizedResponse,
)


def _problem_response(
    problem: ProblemDetailsResponse, headers: Mapping[str, str] | None = None
) -> JSONResponse:
    return JSONResponse(
        status_code=problem.status,
        content=problem.model_dump(exclude_none=True),
        media_type="application/problem+json",
        headers=dict(headers) if headers is not None else None,
    )


def _format_error_loc(loc: Sequence[Any]) -> str:
    """
    Convert FastAPI/Pydantic locations into dotted notation with index suffixes.
    Examples:
      ("body", "play_context", "players") -> "play_context.players"
      ("body", "liked_games", 0) -> "liked_games[0]"
    """
    parts = list(loc)
    if parts and parts[0] in {"body", "query", "path", "header", "cookie"}:
        parts = parts[1:]

    formatted: list[str] = []
    for part in parts:
        if isinstance(part, int) and formatted:
            formatted[-1] = f"{formatted[-1]}[{part}]"
        else:
            formatted.append(str(part))
    return ".".join(formatted) if formatted else ""


def _invalid_params_from_errors(errors: Sequence[dict[str, Any]]) -> list[dict[str, str]]:
    invalid_params: list[dict[str, str]] = []
    for error in errors:
        loc = error.get("loc", ())
        msg = error.get("msg", "Invalid value.")
        name = _format_error_loc(loc if isinstance(loc, Sequence) else ())
        input_value = error.get("input")

        if isinstance(input_value, list) and name and "[" not in name:
            for idx, _ in enumerate(input_value):
                invalid_params.append(
                    {
                        "name": f"{name}[{idx}]",
                        "reason": msg,
                    }
                )
        else:
            invalid_params.append(
                {
                    "name": name or "request",
                    "reason": msg,
                }
            )
    return invalid_params


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    def handle_request_validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        invalid_params = _invalid_params_from_errors(exc.errors())
        problem = BadRequestResponse(
            title=HTTPStatus.BAD_REQUEST.phrase,
            detail="One or more input parameters were invalid.",
            code="VALIDATION_ERROR",
            instance=None,
            invalid_params=invalid_params,
        )
        return _problem_response(problem)

    @app.exception_handler(HTTPException)
    def handle_http_exception(request: Request, exc: HTTPException) -> JSONResponse:
        status_code = exc.status_code
        headers = dict(exc.headers) if hasattr(exc, "headers") and exc.headers else None
        # Prefer custom type/title for standard statuses; fall back to about:blank otherwise.
        if status_code == starlette_status.HTTP_404_NOT_FOUND:
            problem = NotFoundResponse(detail=exc.detail or None)
        elif status_code == starlette_status.HTTP_401_UNAUTHORIZED:
            problem = UnauthorizedResponse(detail=exc.detail or None)
        elif status_code == starlette_status.HTTP_400_BAD_REQUEST:
            problem = BadRequestResponse(
                detail=exc.detail or HTTPStatus.BAD_REQUEST.phrase,
                code="VALIDATION_ERROR",
                invalid_params=None,
            )
        else:
            title = (
                HTTPStatus(status_code).phrase
                if status_code in HTTPStatus._value2member_map_
                else str(exc.detail) or "Error"
            )
            problem = ProblemDetailsResponse(
                title,
                status=status_code,
                detail=exc.detail or None,
            )
        return _problem_response(problem, headers=headers)

    @app.exception_handler(StarletteHTTPException)
    def handle_starlette_http_exception(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        return handle_http_exception(
            request,
            HTTPException(
                status_code=exc.status_code,
                detail=exc.detail,
                headers=dict(exc.headers) if exc.headers else None,
            ),
        )

    @app.exception_handler(InvalidStudyTokenError)
    def handle_invalid_study_token(request: Request, exc: InvalidStudyTokenError) -> JSONResponse:
        problem = BadRequestResponse(
            detail=str(exc) or "Invalid study token.",
            code="INVALID_STUDY_TOKEN",
            invalid_params=None,
        )
        return _problem_response(problem)
