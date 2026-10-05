"""Quiz Bank 원문·정리 결과, 학습 상태와 피드백."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import _now

# Main-Quiz와 문항·일정 구조가 달라 은행 원문, 결과, 학습 상태를 별도로 저장한다.
BANK_RESPONDED = "responded"  # 관리자가 ChatGPT 응답을 저장했다 — 러너를 기다린다
BANK_BUILDING = "building"
BANK_READY = "ready"  # 검증 통과. 학생에게 여는 것은 `open_to_students` 가 따로 정한다
BANK_INVALID = "invalid"  # 정리는 됐는데 검증 오류가 있다 — 관리자가 오류를 본다
BANK_FAILED = "failed"


class QuizBank(Base):
    """강의 하나의 문제은행. 한 편에 한 줄이고 다시 만들면 덮는다(build_id 가 바뀐다)."""

    __tablename__ = "quiz_bank"

    subject: Mapped[str] = mapped_column(Text, primary_key=True)
    run_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    build_id: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=BANK_RESPONDED)
    prompt_version: Mapped[str] = mapped_column(String(16), nullable=False, default="")
    # ChatGPT 응답 원문. **지우지 않는다** — 정리를 다시 돌릴 때 이것만 있으면 된다.
    raw_response: Mapped[str] = mapped_column(Text, nullable=False, default="")
    conversation_url: Mapped[str] = mapped_column(Text, nullable=False, default="")
    responded_by: Mapped[str] = mapped_column(Text, nullable=False, default="")
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    bank: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    validation: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # 외부지식 검토(`quizbank/review.py`). 막지 않고 표시만 한다.
    review: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # 문항 ID → 인용한 필기 쪽들. 답을 볼 때 그 쪽들의 서명 URL 을 낸다.
    pages: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    usage: Mapped[list | None] = mapped_column(JSON, nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # **처음엔 관리자에게만 보인다.** 관리자가 보고 연다 — 새 파이프라인의 첫 은행들이다.
    open_to_students: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    built_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    __table_args__ = (
        ForeignKeyConstraint(
            ["subject", "run_id"], ["lecture.subject", "lecture.run_id"], ondelete="CASCADE"
        ),
    )


class BankState(Base):
    """사용자·강의별 Study Engine 상태 JSON. 순수 함수 엔진이 전체 상태를 갱신한다.

    build_id가 현재 은행과 다르면 기존 상태를 previous로 보관하고 새로 시작한다."""

    __tablename__ = "bank_state"

    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    subject: Mapped[str] = mapped_column(Text, primary_key=True)
    run_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    build_id: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    state: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    previous: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    __table_args__ = (
        ForeignKeyConstraint(
            ["subject", "run_id"], ["lecture.subject", "lecture.run_id"], ondelete="CASCADE"
        ),
    )


class BankFeedback(Base):
    """학생이 푸는 중에 누른 「문제 있음」·「좋은 문제」."""

    __tablename__ = "bank_feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    subject: Mapped[str] = mapped_column(Text, nullable=False)
    run_id: Mapped[str] = mapped_column(String(32), nullable=False)
    build_id: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    question_id: Mapped[str] = mapped_column(String(64), nullable=False)
    category: Mapped[str] = mapped_column(String(16), nullable=False)
    comment: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    __table_args__ = (
        ForeignKeyConstraint(
            ["subject", "run_id"], ["lecture.subject", "lecture.run_id"], ondelete="CASCADE"
        ),
        Index("ix_bank_feedback_lecture", "subject", "run_id"),
    )
