"""Separate immutable content and append-only learner events; no legacy state writes."""
from datetime import datetime
from sqlalchemy import JSON, Boolean, DateTime, DDL, Integer, String, Text, event
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base
from app.models.base import _now


class RootContent(Base):
    __tablename__ = 'root_content'
    subject: Mapped[str] = mapped_column(Text, primary_key=True)
    run_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    revision: Mapped[str] = mapped_column(String(64), primary_key=True)
    document: Mapped[dict] = mapped_column(JSON)
    digest: Mapped[str] = mapped_column(String(64))
    reviewed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class RootControl(Base):
    __tablename__ = 'root_control'
    subject: Mapped[str] = mapped_column(Text, primary_key=True)
    run_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    revision: Mapped[str | None] = mapped_column(String(64), nullable=True)
    allowed_users: Mapped[list] = mapped_column(JSON, default=list)


class RootSession(Base):
    __tablename__ = 'root_session'
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    subject: Mapped[str] = mapped_column(Text)
    run_id: Mapped[str] = mapped_column(String(32))
    revision: Mapped[str] = mapped_column(String(64))
    day: Mapped[str] = mapped_column(String(10))
    policy: Mapped[dict] = mapped_column(JSON)
    tasks: Mapped[list] = mapped_column(JSON)
    state: Mapped[dict] = mapped_column(JSON)
    version: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class RootEvent(Base):
    __tablename__ = 'root_event'
    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    request_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    subject: Mapped[str] = mapped_column(Text)
    run_id: Mapped[str] = mapped_column(String(32))
    revision: Mapped[str] = mapped_column(String(64))
    kind: Mapped[str] = mapped_column(String(16))
    payload: Mapped[dict] = mapped_column(JSON)
    result: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


for model in (RootContent, RootControl, RootSession, RootEvent):
    event.listen(model.__table__, 'after_create', DDL(
        f'ALTER TABLE {model.__tablename__} ENABLE ROW LEVEL SECURITY').execute_if(dialect='postgresql'))
