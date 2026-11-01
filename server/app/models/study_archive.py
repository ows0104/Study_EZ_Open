"""Append-only evidence for bank replacement and study-state recovery."""
from datetime import datetime

from sqlalchemy import DDL, JSON, DateTime, Index, String, Text, event
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import _now


class BankVersion(Base):
    __tablename__ = 'bank_version'
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    subject: Mapped[str] = mapped_column(Text, nullable=False)
    run_id: Mapped[str] = mapped_column(String(32), nullable=False)
    build_id: Mapped[str] = mapped_column(String(64), nullable=False)
    bank: Mapped[dict] = mapped_column(JSON, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False, default='publication')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    __table_args__ = (Index('ix_bank_version_build', 'subject', 'run_id', 'build_id'),)


class BankStateArchive(Base):
    __tablename__ = 'bank_state_archive'
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    subject: Mapped[str] = mapped_column(Text, nullable=False)
    run_id: Mapped[str] = mapped_column(String(32), nullable=False)
    build_id: Mapped[str] = mapped_column(String(64), nullable=False)
    state: Mapped[dict] = mapped_column(JSON, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False, default='replacement')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    __table_args__ = (Index('ix_bank_state_archive_user', 'user_id', 'subject', 'run_id', 'build_id'),)


for model in (BankVersion, BankStateArchive):
    event.listen(model.__table__, 'after_create', DDL(
        f'ALTER TABLE {model.__tablename__} ENABLE ROW LEVEL SECURITY').execute_if(dialect='postgresql'))
