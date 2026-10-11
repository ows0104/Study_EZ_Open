"""Additive study storage. Immutable content/attempts survive bank replacement."""

from sqlalchemy import JSON, BigInteger, Boolean, DDL, Index, Integer, String, Text, event
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class LearningBankVersion(Base):
    __tablename__ = "learning_bank_version"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    subject: Mapped[str] = mapped_column(Text)
    run_id: Mapped[str] = mapped_column(String(32))
    build_id: Mapped[str] = mapped_column(String(64))
    bank: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[int] = mapped_column(BigInteger)


class LearningLegacyState(Base):
    __tablename__ = "learning_legacy_state"
    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    version_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    data: Mapped[dict] = mapped_column(JSON)


class LearningProfile(Base):
    __tablename__ = "learning_profile"
    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    minutes: Mapped[int] = mapped_column(Integer, default=60)
    buffer_days: Mapped[int] = mapped_column(Integer, default=3)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    # Acts as a per-user transaction lock; JSON is a rebuildable projection.
    state: Mapped[dict] = mapped_column(JSON, default=dict)


class LearningDay(Base):
    __tablename__ = "learning_day"
    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    day: Mapped[str] = mapped_column(String(10), primary_key=True)
    plan: Mapped[dict] = mapped_column(JSON)


class LearningSession(Base):
    __tablename__ = "learning_session"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    mode: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16), default="active")
    created_at: Mapped[int] = mapped_column(BigInteger)
    data: Mapped[dict] = mapped_column(JSON)


class LearningAttempt(Base):
    __tablename__ = "learning_attempt"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # served token: idempotency key
    user_id: Mapped[str] = mapped_column(String(64))
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    objective_key: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[int] = mapped_column(BigInteger)
    data: Mapped[dict] = mapped_column(JSON)
    # Undo is a compensating record. Never erase an exposure or original answer.
    undone: Mapped[bool] = mapped_column(Boolean, default=False)
    __table_args__ = (Index("learning_attempt_user_time", "user_id", "created_at"),)


for model in (LearningBankVersion, LearningLegacyState, LearningProfile, LearningDay, LearningSession, LearningAttempt):
    event.listen(model.__table__, "after_create", DDL(
        f"ALTER TABLE {model.__tablename__} ENABLE ROW LEVEL SECURITY").execute_if(dialect="postgresql"))
