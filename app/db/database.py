"""
Database access. SQLAlchemy 2.x with a lazily created engine so tests and
tools can point DATABASE_URL at a temporary SQLite file.

Default: sqlite:///./data/corridorcomply.db (created on first use).
Production: postgresql+psycopg://user:pass@host/db and `alembic upgrade head`.
"""
from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

logger = logging.getLogger(__name__)

_engine: Optional[Engine] = None
_SessionLocal: Optional[sessionmaker] = None


def database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if url:
        return url
    from ..config import BASE_DIR
    path = Path(os.getenv("DATA_DIR", str(BASE_DIR / "data"))) / "corridorcomply.db"
    path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{path}"


def get_engine() -> Engine:
    global _engine, _SessionLocal
    if _engine is None:
        url = database_url()
        kwargs = {"pool_pre_ping": True}
        if url.startswith("sqlite"):
            kwargs["connect_args"] = {"check_same_thread": False}
        _engine = create_engine(url, **kwargs)
        if url.startswith("sqlite"):
            @event.listens_for(_engine, "connect")
            def _fk_on(dbapi_conn, _):  # pragma: no cover - trivial
                dbapi_conn.execute("PRAGMA foreign_keys=ON")
        _SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False)
        logger.info(f"Database: {url.split('@')[-1] if '@' in url else url}")
    return _engine


def init_db() -> None:
    """Create missing tables for SQLite (development).

    Any other database is expected to be migrated with `alembic upgrade head`
    (the Docker image does this on start). Set AUTO_CREATE_TABLES=true to force
    create_all elsewhere, e.g. in a throwaway test database.
    """
    from . import models  # noqa: F401  (registers tables)
    url = database_url()
    if url.startswith("sqlite") or os.getenv("AUTO_CREATE_TABLES", "").lower() == "true":
        models.Base.metadata.create_all(get_engine())


def reset_db() -> None:
    """Forget the engine so the next call re-reads DATABASE_URL (tests)."""
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine, _SessionLocal = None, None


@contextmanager
def session_scope() -> Iterator[Session]:
    get_engine()
    session: Session = _SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_session() -> Iterator[Session]:
    """FastAPI dependency."""
    with session_scope() as s:
        yield s
