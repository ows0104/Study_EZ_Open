"""반 공용 예습 링크, 개인 대화, 링크 열람 기록."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    DDL,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    event,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import _now


class Preview(Base):
    """반 공용 예습 링크. share_url이 기본이며 conversation_url 공개는 설정으로 결정한다."""

    __tablename__ = "preview"

    subject: Mapped[str] = mapped_column(Text, primary_key=True)
    run_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False, default="chatgpt")
    share_url: Mapped[str] = mapped_column(Text, nullable=False, default="")
    conversation_url: Mapped[str] = mapped_column(Text, nullable=False, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    __table_args__ = (
        ForeignKeyConstraint(
            ["subject", "run_id"], ["lecture.subject", "lecture.run_id"], ondelete="CASCADE"
        ),
    )


class UserPreview(Base):
    """개인이 이어서 쓰는 예습 대화. 소유자만 열고 profile.preview_prompt로 묻는다.

    관리자가 공용 링크를 만들 때도 생성자의 conversation_url은 여기에 함께 보관한다."""

    __tablename__ = "user_preview"

    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    subject: Mapped[str] = mapped_column(Text, primary_key=True)
    run_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False, default="chatgpt")
    conversation_url: Mapped[str] = mapped_column(Text, nullable=False, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    __table_args__ = (
        ForeignKeyConstraint(
            ["subject", "run_id"], ["lecture.subject", "lecture.run_id"], ondelete="CASCADE"
        ),
    )


class UserReview(Base):
    """오늘 강의록으로 만든 개인 복습 대화. 예습 링크와 별도로 소유자에게만 제공한다."""

    __tablename__ = "user_review"

    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    subject: Mapped[str] = mapped_column(Text, primary_key=True)
    run_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False, default="chatgpt")
    conversation_url: Mapped[str] = mapped_column(Text, nullable=False, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    __table_args__ = (
        ForeignKeyConstraint(
            ["subject", "run_id"], ["lecture.subject", "lecture.run_id"], ondelete="CASCADE"
        ),
    )


# Supabase의 공개 API에서는 직접 읽지 못한다. 서버의 DB 역할은 RLS를 우회하고,
# HTTP 경로에서 로그인한 소유자를 확인한다. SQLite 로컬 검사에는 적용하지 않는다.
event.listen(
    UserReview.__table__,
    "after_create",
    DDL("ALTER TABLE user_review ENABLE ROW LEVEL SECURITY").execute_if(dialect="postgresql"),
)


# 예습 링크는 둘이다. **같은 표에 갈래로 둔다** — 「기본을 읽는 사람과 자기
# 대화를 쓰는 사람이 갈리나」가 이 둘을 나란히 놓아야만 보인다.
PREVIEW_OPEN_SHARE = "share"  # 반 전체가 읽는 기본 링크
PREVIEW_OPEN_MINE = "mine"  # 자기 대화
PREVIEW_OPEN_KINDS = (PREVIEW_OPEN_SHARE, PREVIEW_OPEN_MINE)
PREVIEW_ACTION_KINDS = (*PREVIEW_OPEN_KINDS, "create")  # personal creation attempt, not completion


class PreviewOpen(Base):
    """우리 화면에서 공용·개인 예습 링크를 클릭한 기록. 공유받은 URL의 직접 열람은 제외한다.

    표 생성 전의 기록은 없으므로 이용현황은 집계 시작 시각 opensSince를 함께 제공한다."""

    __tablename__ = "preview_open"

    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    subject: Mapped[str] = mapped_column(Text, primary_key=True)
    run_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    kind: Mapped[str] = mapped_column(String(8), primary_key=True)  # PREVIEW_OPEN_KINDS
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    first_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    last_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    __table_args__ = (Index("ix_preview_open_user", "user_id", "last_at"),)
