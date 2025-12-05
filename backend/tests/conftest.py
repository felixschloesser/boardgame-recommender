from __future__ import annotations

from typing import Iterator

import pytest
from boardgames_api.app import app
from boardgames_api.persistence import database
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def client() -> Iterator[TestClient]:
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _temp_db(monkeypatch, tmp_path):
    """
    Use a temporary SQLite database per test to avoid state bleed.
    """
    db_path = tmp_path / "app.sqlite3"
    monkeypatch.setenv("BOARDGAMES_DB_PATH", str(db_path))
    monkeypatch.setattr(database, "_engine", None, raising=False)
    yield
    # cleanup engine after test
    monkeypatch.setattr(database, "_engine", None, raising=False)
