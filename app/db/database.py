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
        engine = get_engine()
        models.Base.metadata.create_all(engine)
        _add_missing_columns(engine, models.Base.metadata)


def _add_missing_columns(engine, metadata) -> None:
    """Bring a create_all-managed SQLite database up to the current models.

    create_all never alters an existing table, so a laptop database created by an
    older version lacks columns added since (e.g. decisions.beneficiary_screening_id)
    and every query on that table fails. Add the missing nullable columns in place.
    Constraints cannot be added this way; Alembic remains the path for Postgres.
    """
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    with engine.begin() as conn:
        for table in metadata.sorted_tables:
            if table.name not in existing_tables:
                continue
            present = {c["name"] for c in inspector.get_columns(table.name)}
            for col in table.columns:
                if col.name in present:
                    continue
                if not col.nullable and col.default is None and col.server_default is None:
                    logger.warning("Cannot add NOT NULL column %s.%s without a default; run alembic", table.name, col.name)
                    continue
                ddl = f'ALTER TABLE "{table.name}" ADD COLUMN "{col.name}" {col.type.compile(dialect=engine.dialect)}'
                if col.server_default is not None:
                    ddl += f" DEFAULT {col.server_default.arg}"
                conn.execute(text(ddl))
                logger.info("Added missing column %s.%s", table.name, col.name)


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
