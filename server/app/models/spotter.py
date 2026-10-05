"""땡시 풀이 기록, 신고, 글타래와 댓글."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import _now

# 앱 접근 권한은 accounts.APP_POLICY와 auth.require_spotter가 정한다.

# 제보의 갈래. 화면의 선택지와 같은 순서다.
SPOTTER_REPORT_KINDS = ("answer", "image", "explanation", "options", "other")
SPOTTER_REPORT_OPEN = "open"
SPOTTER_REPORT_RESOLVED = "resolved"
SPOTTER_REPORT_WONTFIX = "wontfix"
SPOTTER_REPORT_STATUSES = frozenset(
    {SPOTTER_REPORT_OPEN, SPOTTER_REPORT_RESOLVED, SPOTTER_REPORT_WONTFIX}
)

# 한 사람이 들고 다니는 기록의 수. 브라우저에 쌓던 시절과 같은 수다.
SPOTTER_RECORD_KEEP = 30

# 신고자 수가 이 값에 도달하면 경보·문항 제외·글타래 생성이 함께 적용된다.
# 사용자·문항당 신고 하나이므로 열린 신고 수가 곧 신고자 수다.
SPOTTER_ALERT_MIN = 1

# 글타래가 무엇에 걸렸는가. 문항 하나가 이상한 것과 사진 한 장이 이상한 것은
# 고치는 일이 달라서(보기를 고친다 / 사진을 다시 자른다) 따로 선다.
SPOTTER_THREAD_QUESTION = "question"
SPOTTER_THREAD_IMAGE = "image"
SPOTTER_THREAD_KINDS = (SPOTTER_THREAD_QUESTION, SPOTTER_THREAD_IMAGE)

# 댓글 한 줄의 길이. 게시판이지 논문이 아니다.
SPOTTER_COMMENT_MAX = 2000


class SpotterRecord(Base):
    """땡시 한 판의 시각·모드·점수. 문항별 오답 상태는 SpotterWrong에 둔다."""

    __tablename__ = "spotter_record"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    mode: Mapped[str] = mapped_column(String(8), nullable=False, default="exam")  # exam|study
    score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    __table_args__ = (Index("ix_spotter_record_user", "user_id", "created_at"),)


class SpotterWrong(Base):
    """아직 못 맞힌 문항. 맞히면 삭제한다. question_id는 문항 내용의 해시다.

    재빌드로 사라진 문항 ID는 화면에서 제외하며 서버가 문항 DB를 읽어 청소하지 않는다."""

    __tablename__ = "spotter_wrong"

    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    question_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    missed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


class SpotterReport(Base):
    """사용자·문항당 신고 하나. 재신고하면 갱신하며 신고자 수로 경보를 판단한다.

    stem·answer·image는 신고 당시 문면이다. 문항 재빌드 후에도 제보 내용을 보존한다."""

    __tablename__ = "spotter_report"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    question_id: Mapped[str] = mapped_column(String(16), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False, default="other")
    note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # 제보 당시의 문면. 위 설명을 보라 — 현재 문항이 아니다.
    stem: Mapped[str] = mapped_column(Text, nullable=False, default="")
    answer: Mapped[str] = mapped_column(Text, nullable=False, default="")
    image: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # 사진 파일명만, 쉼표로 이어서. 바로 위의 `image`는 **사람이 읽는 줄**이라
    # 출처가 괄호로 붙어 있고, 이것은 **묶어 세는 값**이다.
    #
    # 둘로 나눈 까닭은 한 사진이 여러 문항에 쓰이기 때문이다. 「이 사진이
    # 흐리다」는 제보는 그 사진을 쓰는 문항마다 흩어져 들어와서, 문항으로만
    # 세면 어느 쪽도 임계값을 못 넘은 채 사진 하나가 계속 돌아다닌다.
    # 표시용 문자열을 갈라 읽는 대신 칼럼을 하나 둔다 — 화면에 붙이는 글이
    # 바뀔 때마다 세는 쪽이 조용히 틀리면 안 된다.
    images: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=SPOTTER_REPORT_OPEN)
    admin_note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    __table_args__ = (
        UniqueConstraint("user_id", "question_id", name="uq_spotter_report_user_question"),
        Index("ix_spotter_report_triage", "status", "created_at"),
        Index("ix_spotter_report_question", "question_id"),
    )


class SpotterThread(Base):
    """신고가 SPOTTER_ALERT_MIN에 도달하면 자동 생성되는 문항·사진 글타래.

    열려 있는 문항은 새 세트에서 제외한다. 사진 글타래는 그 사진을 쓰는 모든 문항을
    가리키며, 문항 재빌드 후에도 토론을 읽을 수 있도록 당시 문면을 보존한다."""

    __tablename__ = "spotter_thread"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(String(16), nullable=False, default=SPOTTER_THREAD_QUESTION)
    # 문항 글타래면 question_id, 사진 글타래면 파일명.
    subject: Mapped[str] = mapped_column(String(300), nullable=False)
    stem: Mapped[str] = mapped_column(Text, nullable=False, default="")
    answer: Mapped[str] = mapped_column(Text, nullable=False, default="")
    images: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=SPOTTER_REPORT_OPEN)
    # 관리자가 내린 결론. 닫을 때 한 줄 적는 자리다.
    verdict: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    __table_args__ = (
        UniqueConstraint("kind", "subject", name="uq_spotter_thread_subject"),
        Index("ix_spotter_thread_status", "status", "updated_at"),
    )


class SpotterComment(Base):
    """글타래 의견. 삭제할 때 행은 남기고 본문만 비워 대화 흐름을 보존한다."""

    __tablename__ = "spotter_comment"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    thread_id: Mapped[int] = mapped_column(Integer, nullable=False)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    __table_args__ = (Index("ix_spotter_comment_thread", "thread_id", "created_at"),)
