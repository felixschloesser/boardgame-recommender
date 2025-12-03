from fastapi import HTTPException, Request, Security
from fastapi.security import APIKeyCookie
from starlette import status

# Security scheme so endpoints show lock icon in OpenAPI and set cookie auth.
session_cookie_scheme = APIKeyCookie(name="session_id", auto_error=False)


def _get_session(request: Request) -> dict:
    return request.session if isinstance(request.session, dict) else {}


def require_session(
    request: Request, session_id: str | None = Security(session_cookie_scheme)
) -> str:
    """
    Required session dependency; raises 401 when missing or invalid.
    """
    session = _get_session(request)
    participant_id = session.get("participant_id")
    if not participant_id or session_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Valid session cookie is required.",
        )
    return participant_id


def invalidate_session(
    request: Request, session_id: str | None = Security(session_cookie_scheme)
) -> str:
    """
    Dependency that validates and then clears a session, raising 401 on invalid/missing.
    Returns the participant id when successful.
    """
    participant_id = require_session(request, session_id)
    session = _get_session(request)
    session.clear()
    # SessionMiddleware will overwrite the cookie to reflect the cleared state.
    return participant_id
