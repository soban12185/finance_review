"""Database session management.

The application connects to the PostgreSQL database supplied through
``DATABASE_URL``.  SQLite is only used by the test-suite (via ``TEST_DATABASE_URL``
or by overriding the engine) so that financial logic can be tested deterministically.
"""
from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

_settings = get_settings()


def build_engine(database_url: str | None = None, *, echo: bool = False) -> Engine:
    url = database_url or _settings.database_url
    kwargs: dict = {"connect_args": {}}
    if url.startswith("sqlite"):
        kwargs["connect_args"]["check_same_thread"] = False
    engine = create_engine(url, echo=echo, pool_pre_ping=True, future=True, **kwargs)
    if url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def _set_sqlite_pragma(dbapi_connection, connection_record):  # pragma: no cover - test only
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
    return engine


engine: Engine = build_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db() -> Iterator[Session]:
    """FastAPI dependency that provides a request-scoped session."""
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def session_scope() -> Session:
    """Return a new standalone session (used by scripts / workers)."""
    return SessionLocal()