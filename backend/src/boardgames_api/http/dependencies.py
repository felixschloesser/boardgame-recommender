from __future__ import annotations

from typing import Iterator

from sqlalchemy.orm import Session

from boardgames_api.persistence.database import get_session


def db_session() -> Iterator[Session]:
    """
    FastAPI dependency for database sessions.
    Yields a Session and ensures cleanup. Commit/rollback should be controlled by callers.
    """
    session = get_session()
    try:
        yield session
    finally:
        session.close()
