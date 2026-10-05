"""예습·복습 카드, 관리자 수정, 복습 일정과 되돌리기 기록."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, declared_attr, mapped_column

from app.database import Base
from app.models.base import _now


class _QuizItem:
    """예습·복습의 공통 자유회상 카드. 채점은 사용자가 하고 답·해설은 reveal로만 보낸다.

    두 갈래 모두 item_id를 c001부터 사용하므로 표를 분리하고 칼럼 정의를 공유한다.
    운영 DB의 기본키를 유지하기 위해 하나의 표로 합치지 않는다."""

    subject: Mapped[str] = mapped_column(Text, primary_key=True)
    run_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    item_id: Mapped[str] = mapped_column(String(32), primary_key=True)  # "c001"
    ord: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # basic | cloze | ox. 푸는 방식은 셋 다 같고 화면이 꼴만 달리 그린다.
    qtype: Mapped[str] = mapped_column(String(16), nullable=False)
    stem: Mapped[str] = mapped_column(Text, nullable=False)
    # 빈칸 카드의 원문(`{{c1::…}}`). 웹은 `stem`(편 것)을 그리고, 사이트에서 고칠 때는
    # 이것을 고친다 — 답이 질문 안에 있어서 편 것을 고쳐서는 덱으로 못 되돌린다
    # (`quizgen/site_edits.py`). 빈칸이 아니면 빈 문자열. 2026-09-23.
    source_stem: Mapped[str] = mapped_column(Text, nullable=False, default="")
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    # 예습은 **왜 이것이 「꼭 반드시」인가**(spine·vocabulary·mechanism·clinical·
    # repeated), 복습은 등급(`importance`)이 온다. 파이프라인이 그 갈림을 안다.
    focus: Mapped[str] = mapped_column(String(16), nullable=False, default="")
    # 무엇을 막는 카드인가. term·abbrev·mechanism·taxonomy·clinical·number 등.
    card_type: Mapped[str] = mapped_column(String(16), nullable=False, default="")
    exam_hit: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    slide_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_type: Mapped[str] = mapped_column(String(16), nullable=False, default="lecture")
    source_anchor: Mapped[str] = mapped_column(Text, nullable=False, default="")
    explanation: Mapped[str] = mapped_column(Text, nullable=False, default="")
    flags: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    # 예습만 채운다(2026-10-04 관리자). **왜 이 문제를 냈나** — 생소한 문제를 본 학생이
    # 「이것까지 알아야 하나?」 싶지 않게 한다. 그리고 도전 문제인가.
    # 앞면에는 유형 배지(`why_tags`)만 뜨고 글은 답을 편 뒤에 온다(`reveal`).
    why_asked: Mapped[str] = mapped_column(Text, nullable=False, default="")
    challenge: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # 「왜 냈나」의 유형 — exam·clinical·later·annotation·basis. 앞면에 배지로 뜬다.
    # 이름표는 화면이 든다(`web/src/lecture/Quiz.tsx`). 모르는 값은 화면이 안 그린다.
    why_tags: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    @declared_attr.directive
    def __table_args__(cls) -> tuple:
        return (
            ForeignKeyConstraint(
                ["subject", "run_id"], ["lecture.subject", "lecture.run_id"], ondelete="CASCADE"
            ),
            Index(f"ix_{cls.__tablename__}_lecture", "subject", "run_id"),
        )


class PreItem(_QuizItem, Base):
    """`pre_items.final.json`의 예습 카드 하나."""

    __tablename__ = "pre_item"


class MainItem(_QuizItem, Base):
    """`main_items.final.json`의 복습 카드. 업로드된 문항이 없는 강의는 덱만 제공한다."""

    __tablename__ = "main_item"


# 사람이 사이트에서 카드 한 장에 내린 판정.
CARD_OK = "ok"  # 보고 괜찮다고 했다 — 내용은 파이프라인이 올린 그대로
CARD_EDIT = "edit"  # 문구를 고쳤다
CARD_DELETE = "delete"  # 뺐다
CARD_ACTIONS = (CARD_OK, CARD_EDIT, CARD_DELETE)


class CardEdit(Base):
    """관리자의 카드 확인·수정·삭제 판정. 업로드로 문항이 교체될 때 다시 적용한다.

    다음 업로드의 원본이 original과 달라지면 이전 판정을 버린다. 같은 item_id라도
    새 내용에 과거 수정을 덮어쓰면 안 된다."""

    __tablename__ = "card_edit"

    subject: Mapped[str] = mapped_column(Text, primary_key=True)
    run_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    quiz_kind: Mapped[str] = mapped_column(String(8), primary_key=True)  # main|pre
    item_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    action: Mapped[str] = mapped_column(String(8), nullable=False)  # CARD_ACTIONS
    # 고친 칸만 찬다. None 이면 원본 그대로다.
    stem: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 빈칸 카드는 원문을 고친다. `stem` 에는 그것을 편 것이 같이 찬다.
    source_stem: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 파이프라인이 마지막으로 올린 카드 그대로(`ord` 포함). 되돌리기와 「바꿔 올렸나」
    # 둘 다 이것을 본다.
    original: Mapped[dict] = mapped_column(JSON, nullable=False)
    edited_by: Mapped[str] = mapped_column(String(320), nullable=False, default="")
    edited_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    __table_args__ = (
        ForeignKeyConstraint(
            ["subject", "run_id"], ["lecture.subject", "lecture.run_id"], ondelete="CASCADE"
        ),
    )


class _Attempt:
    """사용자별 카드의 자기 채점과 복습 일정. 일정 계산은 app.srs가 담당한다.

    correct는 again만 False인 사용자 응답이며 서버의 정답 판정이 아니다.
    예습·복습은 item_id가 겹쳐 별도 표를 사용한다."""

    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    subject: Mapped[str] = mapped_column(Text, primary_key=True)
    run_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    item_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    correct: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    answered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    # ── 여기부터가 일정이다(2026-09-18). 값을 정하는 것은 `app/srs.py` 하나뿐이고,
    # 이름도 그쪽 `Card` 와 같다. **한 줄이 한 카드의 전부라 되돌리기가 이 일곱
    # 칼럼을 그대로 적어 두면 된다**(`_ReviewLog`).
    #
    # 옛 줄에는 이 칼럼이 없다. 기본값이 new·0·2.5 이므로 그런 줄은 「한 번
    # 찍었지만 일정은 아직 없다」로 읽힌다 — `correct` 는 그대로 있으므로
    # 「놓친 것」과 진행 수는 옛 줄에서도 계속 나온다.
    state: Mapped[str] = mapped_column(String(10), nullable=False, default="new")
    step: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    interval_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ease: Mapped[float] = mapped_column(Float, nullable=False, default=2.5)
    reps: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    lapses: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    #: 언제 다시 낼 것인가. `None` 이면 아직 일정이 없는 것이라 바로 낸다.
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    @declared_attr.directive
    def __table_args__(cls) -> tuple:
        return (
            Index(f"ix_{cls.__tablename__}_user_lecture", "user_id", "subject", "run_id"),
            # 「지금 낼 것」을 고르는 질의가 이 순서로 훑는다.
            Index(f"ix_{cls.__tablename__}_due", "user_id", "due_at"),
        )


class QuizAttempt(_Attempt, Base):
    """예습 카드의 웹 풀이 상태. 운영 테이블 이름 quiz_attempt를 유지한다."""

    __tablename__ = "quiz_attempt"


class MainAttempt(_Attempt, Base):
    """복습 카드의 웹 풀이 상태. Anki에서 공부한 진행은 포함하지 않는다."""

    __tablename__ = "main_attempt"


class _ReviewLog:
    """채점 직전 상태를 보관하는 undo 기록. SM-2 계산으로 역산하지 않는다.

    had_attempt=False이면 첫 채점이므로 undo 때 시도 행 자체를 삭제한다.
    item_id가 겹치는 예습·복습은 별도 표를 사용한다."""

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    subject: Mapped[str] = mapped_column(Text, nullable=False)
    run_id: Mapped[str] = mapped_column(String(32), nullable=False)
    item_id: Mapped[str] = mapped_column(String(32), nullable=False)
    #: again | hard | good | easy. `srs.GRADES` 와 같다.
    grade: Mapped[str] = mapped_column(String(8), nullable=False)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    had_attempt: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    prev_correct: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    prev_state: Mapped[str] = mapped_column(String(10), nullable=False, default="new")
    prev_step: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    prev_interval_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    prev_ease: Mapped[float] = mapped_column(Float, nullable=False, default=2.5)
    prev_reps: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    prev_lapses: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    prev_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    @declared_attr.directive
    def __table_args__(cls) -> tuple:
        return (
            # 되돌리기는 언제나 「이 사람 이 강의의 마지막 줄」을 집는다.
            Index(f"ix_{cls.__tablename__}_undo", "user_id", "subject", "run_id", "id"),
        )


class PreReviewLog(_ReviewLog, Base):
    """Pre-Quiz 웹 풀이의 되돌리기 기록."""

    __tablename__ = "pre_review_log"


class MainReviewLog(_ReviewLog, Base):
    """Main-Quiz 웹 풀이의 되돌리기 기록."""

    __tablename__ = "main_review_log"
