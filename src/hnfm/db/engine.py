"""Engine/session management for the hn.fm Postgres data store."""

import logging
import os
import threading
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger(__name__)

DEFAULT_DATABASE_URL = "postgresql+psycopg://hnfm:hnfm@localhost:5432/hnfm"

_lock = threading.Lock()
_engine = None
_session_factory = None


def get_database_url() -> str:
    return os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)


def get_engine():
    global _engine, _session_factory
    if _engine is None:
        with _lock:
            if _engine is None:
                _engine = create_engine(get_database_url(), pool_pre_ping=True)
                if _engine.dialect.name == "sqlite":
                    # sqlite (tests) disables FK enforcement by default; the
                    # cascades in the schema depend on it.
                    from sqlalchemy import event

                    @event.listens_for(_engine, "connect")
                    def _fk_pragma(dbapi_conn, _record):
                        dbapi_conn.execute("PRAGMA foreign_keys=ON")

                _session_factory = sessionmaker(bind=_engine, expire_on_commit=False)
    return _engine


def reset_engine() -> None:
    """Dispose the engine so the next use re-reads DATABASE_URL (tests)."""
    global _engine, _session_factory
    with _lock:
        if _engine is not None:
            _engine.dispose()
        _engine = None
        _session_factory = None


@contextmanager
def db_session():
    """Short-lived session: commit on success, rollback on error."""
    get_engine()
    session = _session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def ensure_schema() -> None:
    """Create tables if missing (dev convenience; Alembic owns evolution).

    Gated on HNFM_DB_AUTO_CREATE (default true). create_all is idempotent and
    matches Alembic migration 0001; disable in environments managed by Alembic.
    """
    if os.getenv("HNFM_DB_AUTO_CREATE", "true").lower() != "true":
        return
    from .orm import Base

    try:
        Base.metadata.create_all(get_engine())
    except Exception as e:
        logger.error(f"ensure_schema failed: {e}")
        raise
