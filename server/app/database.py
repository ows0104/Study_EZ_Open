from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


def _normalize_database_url(url: str) -> str:
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://") :]
    if url.startswith("postgresql://") and "+" not in url.split("://", 1)[0]:
        return "postgresql+psycopg://" + url[len("postgresql://") :]
    return url


def _engine_options(url: str) -> dict:
    options = {"pool_pre_ping": True, "pool_recycle": 300}
    if url.startswith("postgresql+psycopg://"):
        # Supabase's transaction pooler can move a logical connection between
        # PostgreSQL sessions, so server-side prepared statements are unsafe.
        options["connect_args"] = {"prepare_threshold": None}
    return options


database_url = _normalize_database_url(get_settings().database_url)
engine = create_engine(database_url, **_engine_options(database_url))
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, class_=Session)


def get_db() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
