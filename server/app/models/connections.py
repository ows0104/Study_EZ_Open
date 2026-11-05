"""Versioned connection content and account-scoped append-only learning events."""
from datetime import datetime
from sqlalchemy import JSON, DDL, DateTime, Integer, String, Text, Boolean, event
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base
from app.models.base import _now


class ConnectionContent(Base):
    __tablename__ = 'connection_content'
    subject: Mapped[str] = mapped_column(Text, primary_key=True)
    run_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    revision: Mapped[str] = mapped_column(String(64), primary_key=True)
    document: Mapped[dict] = mapped_column(JSON)
    published: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class ConnectionState(Base):
    __tablename__ = 'connection_state'
    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    subject: Mapped[str] = mapped_column(Text, primary_key=True)
    run_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    revision: Mapped[str] = mapped_column(String(64), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, default=0)
    state: Mapped[dict] = mapped_column(JSON, default=dict)


class ConnectionEvent(Base):
    __tablename__ = 'connection_event'
    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    request_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    subject: Mapped[str] = mapped_column(Text)
    run_id: Mapped[str] = mapped_column(String(32))
    revision: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict] = mapped_column(JSON)
    result: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


for model in (ConnectionContent, ConnectionState, ConnectionEvent):
    event.listen(model.__table__, 'after_create', DDL(
        f'ALTER TABLE {model.__tablename__} ENABLE ROW LEVEL SECURITY').execute_if(dialect='postgresql'))
