"""Explicit authoring requests, frozen inputs and retained generation evidence."""
from datetime import datetime
from sqlalchemy import JSON, DDL, DateTime, Integer, String, Text, UniqueConstraint, event
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base
from app.models.base import _now


class RootGeneration(Base):
    __tablename__ = 'root_generation'
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    job_id: Mapped[int] = mapped_column(Integer, unique=True)
    subject: Mapped[str] = mapped_column(Text)
    run_id: Mapped[str] = mapped_column(String(32))
    user_id: Mapped[str] = mapped_column(String(64))
    request_id: Mapped[str] = mapped_column(String(64))
    input_digest: Mapped[str] = mapped_column(String(64))
    packet: Mapped[dict] = mapped_column(JSON)
    baseline: Mapped[str] = mapped_column(String(64))
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    result_digest: Mapped[str | None] = mapped_column(String(64), nullable=True)
    web_dispatch: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    web_response: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    __table_args__ = (UniqueConstraint('user_id', 'request_id'), UniqueConstraint('subject', 'run_id', 'input_digest'))


event.listen(RootGeneration.__table__, 'after_create', DDL(
    'ALTER TABLE root_generation ENABLE ROW LEVEL SECURITY').execute_if(dialect='postgresql'))
