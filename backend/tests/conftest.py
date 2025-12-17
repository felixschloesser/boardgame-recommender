from __future__ import annotations

from typing import Iterator

import pytest
from boardgames_api.app import app
from boardgames_api.infrastructure import database
from fastapi.testclient import TestClient


@pytest.fixture()
def client(_temp_db) -> Iterator[TestClient]:
    """
    Function-scoped client so each test uses its own isolated temp DB.
    """
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _temp_db(monkeypatch, tmp_path):
    """
    Use a temporary SQLite database per test to avoid state bleed.
    """
    original_default = database.DEFAULT_DB_PATH
    db_path = tmp_path / "app.sqlite3"
    monkeypatch.setenv("BOARDGAMES_DB_PATH", str(db_path))
    monkeypatch.setenv("BOARDGAMES_ENABLE_BGG", "false")
    monkeypatch.setenv("BGG_FETCH_ENABLED", "0")
    # Reset database module state so new engine/sessionmaker use the temp path.
    monkeypatch.setattr(database, "DEFAULT_DB_PATH", db_path, raising=False)
    monkeypatch.setattr(database, "_engine", None, raising=False)
    monkeypatch.setattr(database, "SessionLocal", None, raising=False)
    yield
    # cleanup engine after test
    monkeypatch.setattr(database, "_engine", None, raising=False)
    monkeypatch.setattr(database, "SessionLocal", None, raising=False)
    monkeypatch.setattr(database, "DEFAULT_DB_PATH", original_default, raising=False)
