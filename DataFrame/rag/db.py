from __future__ import annotations

from contextlib import contextmanager
from functools import lru_cache
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from .config import Settings


@lru_cache(maxsize=4)
def _engine_for_url(database_url: str):
    return create_engine(database_url, pool_pre_ping=True, future=True)


def get_engine(settings: Settings):
    if not settings.database_url:
        raise RuntimeError("Нужен DATABASE_URL для работы с PostgreSQL")
    return _engine_for_url(settings.database_url)


def get_session_factory(settings: Settings) -> sessionmaker[Session]:
    engine = get_engine(settings)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


@contextmanager
def session_scope(settings: Settings) -> Iterator[Session]:
    factory = get_session_factory(settings)
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
