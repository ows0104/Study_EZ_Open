"""족보 오답노트(2026-11-14). 사람·족보 문항마다 한 줄.

족보 문서는 R2에 있다(`routes/jokbo.py`). 여기에는 그 문항을 **이 사람이 어떻게 풀었고
오답노트에 어떤 표시를 했는지**만 둔다. 문항 id(`pe_2023_12_030`)는 족보 원천의 id라
족보를 다시 빌드해도 그대로다(합친 문제는 대표 문항의 `mergedFrom`에 남는다).

band  오답노트 표시. high 틀림 · mid 좁혀서 · low 헷갈림 · NULL 표시 없음.
      족보 퀴즈에서 틀리면 high가 붙고, 사람이 손으로 바꾸거나 뗀다.

`jokbo_round`(2026-11-14): 족보 1회독 = 한 줄. 진입 화면에서 고른 범위를 끝까지 풀고 마무리 화면에
닿으면 웹이 한 줄을 더한다(「틀린 문제 다시」는 세지 않는다). 시간표 칸(event_id)에 붙는다 — 족보가 칸에 붙으므로.
"""

from datetime import datetime

from sqlalchemy import DDL, DateTime, Index, Integer, String, event
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import _now

BANDS = ("high", "mid", "low")


class JokboMark(Base):
    __tablename__ = "jokbo_mark"

    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    item_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    event_id: Mapped[str] = mapped_column(String(64), nullable=False)
    band: Mapped[str | None] = mapped_column(String(8), nullable=True)
    wrong_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    right_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_result: Mapped[str | None] = mapped_column(String(12), nullable=True)  # correct|wrong|ungraded
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    marked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    __table_args__ = (Index("ix_jokbo_mark_user_band", "user_id", "band"),)


class JokboRound(Base):
    __tablename__ = "jokbo_round"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    event_id: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)

    __table_args__ = (Index("ix_jokbo_round_user_event", "user_id", "event_id"),)


# Supabase 공개 API에서는 못 읽는다. 서버 DB 역할은 RLS를 우회하고 HTTP 경로가 소유자를 확인한다.
for _table in (JokboMark.__table__, JokboRound.__table__):
    event.listen(_table, "after_create",
                 DDL(f"ALTER TABLE {_table.name} ENABLE ROW LEVEL SECURITY").execute_if(dialect="postgresql"))
