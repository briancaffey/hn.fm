"""Shared test fixtures: an isolated sqlite database per test.

The app runs on Postgres; tests use sqlite through the same SQLAlchemy layer
(JSON columns fall back from JSONB automatically, and repo.next_counter has a
non-PG code path).
"""

import pytest

from ..db import engine as db_engine
from ..db.orm import Base


@pytest.fixture(autouse=True)
def test_db(tmp_path, monkeypatch):
    """Point DATABASE_URL at a fresh sqlite file and create the schema."""
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    db_engine.reset_engine()
    Base.metadata.create_all(db_engine.get_engine())
    yield
    db_engine.reset_engine()


@pytest.fixture(autouse=True)
def outputs_root(tmp_path, monkeypatch):
    """Isolated outputs directory for disk mirrors."""
    out = tmp_path / "outputs"
    out.mkdir()
    monkeypatch.setenv("OUTPUTS_DIR", str(out))
    monkeypatch.setenv("OUTPUTS_ROOT", str(out))
    return str(out)


@pytest.fixture(autouse=True)
def no_object_store(monkeypatch):
    """Keep tests hermetic: never talk to MinIO."""
    monkeypatch.setenv("MEDIA_UPLOAD_ENABLED", "false")
    from ..storage import object_store

    object_store.reset()
