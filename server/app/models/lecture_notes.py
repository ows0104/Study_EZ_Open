"""강의별 개인 기록: 강의록 회독과 짧은 메모(2026-11-10, UI/UX 개편 2단계).

둘 다 본인만 읽고 쓴다. 학습률·복습 간격(SRS)에는 섞지 않는다.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DDL, DateTime, ForeignKeyConstraint, Index, String, Text, event
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import _now


class NoteRead(Base):
    """강의록 1회독 = 한 줄. 패널의 「+」가 한 줄을 더하고, 토막을 누르면 최근 한 줄을 지운다."""

    __tablename__ = "note_read"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    subject: Mapped[str] = mapped_column(Text, nullable=False)
    run_id: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(
            ["subject", "run_id"], ["lecture.subject", "lecture.run_id"], ondelete="CASCADE"
        ),
        Index("ix_note_read_user_lecture", "user_id", "subject", "run_id"),
    )


class LectureMemo(Base):
    """강의 패널의 2~3줄 메모. 사람·강의마다 하나다."""

    __tablename__ = "lecture_memo"

    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    subject: Mapped[str] = mapped_column(Text, primary_key=True)
    run_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    __table_args__ = (
        ForeignKeyConstraint(
            ["subject", "run_id"], ["lecture.subject", "lecture.run_id"], ondelete="CASCADE"
        ),
    )


# Supabase 공개 API에서는 못 읽는다. 서버 DB 역할은 RLS를 우회하고 HTTP 경로가 소유자를 확인한다.
for _table in (NoteRead.__table__, LectureMemo.__table__):
    event.listen(
        _table,
        "after_create",
        DDL(f"ALTER TABLE {_table.name} ENABLE ROW LEVEL SECURITY").execute_if(dialect="postgresql"),
    )
