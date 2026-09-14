"""내 기록. 한 판을 끝낼 때 들어오고, 기기가 바뀌면 합친다."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.auth import CurrentUser
from app.database import get_db
from app.models import (
    SPOTTER_RECORD_KEEP,
    SpotterRecord,
    SpotterWrong,
)
from app.routes.spotter.common import (
    _iso,
    require_spotter,
)

router = APIRouter()


# ── 내 기록 ──────────────────────────────────────────────────────────


def _state(db: Session, user_id: str) -> dict[str, Any]:
    records = db.scalars(
        select(SpotterRecord)
        .where(SpotterRecord.user_id == user_id)
        .order_by(SpotterRecord.created_at.desc(), SpotterRecord.id.desc())
        .limit(SPOTTER_RECORD_KEEP)
    ).all()
    wrong = db.scalars(select(SpotterWrong.question_id).where(SpotterWrong.user_id == user_id)).all()
    return {
        "records": [
            {
                "id": row.id,
                "mode": row.mode,
                "score": row.score,
                "total": row.total,
                "at": _iso(row.created_at),
            }
            for row in records
        ],
        "wrong": list(wrong),
    }


@router.get("/state")
def read_state(
    user: CurrentUser = Depends(require_spotter), db: Session = Depends(get_db)
) -> dict[str, Any]:
    """기록과 오답노트. 로그인하면 어느 기기에서든 같은 것이 나온다."""
    return _state(db, user.id)


class FinishIn(BaseModel):
    mode: str = "exam"
    score: int = 0
    total: int = 0
    # 이번 판에서 틀린 것과 맞힌 것. 맞힌 것을 같이 보내는 이유는 오답노트에서
    # **빼기 위해서**다 — 맞혔다는 사실은 이 목록에만 있다.
    wrong: list[str] = Field(default_factory=list)
    right: list[str] = Field(default_factory=list)


@router.post("/finish")
def finish(
    payload: FinishIn,
    user: CurrentUser = Depends(require_spotter),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """한 판이 끝났다. 기록을 남기고 오답노트를 고친다.

    **한 번의 왕복이다.** 화면이 채점하는 순간 하는 일이 「기록 추가·오답
    추가·정답 제거」 셋인데, 경로를 셋으로 가르면 중간에 하나가 실패했을 때
    오답노트만 반쯤 갱신된 상태가 남는다.
    """
    total = max(0, payload.total)
    if total:
        db.add(
            SpotterRecord(
                user_id=user.id,
                mode="study" if payload.mode == "study" else "exam",
                score=max(0, min(payload.score, total)),
                total=total,
            )
        )

    wrong = {q for q in payload.wrong if q}
    right = {q for q in payload.right if q} - wrong
    if right:
        db.execute(
            delete(SpotterWrong).where(
                SpotterWrong.user_id == user.id, SpotterWrong.question_id.in_(right)
            )
        )
    if wrong:
        have = set(
            db.scalars(
                select(SpotterWrong.question_id).where(
                    SpotterWrong.user_id == user.id, SpotterWrong.question_id.in_(wrong)
                )
            ).all()
        )
        for qid in wrong - have:
            db.add(SpotterWrong(user_id=user.id, question_id=qid))

    # 기록은 최근 것만 든다. 오래된 줄은 화면이 안 그리고, 그대로 두면 한 사람이
    # 학기 내내 푼 판이 전부 쌓인다.
    stale = db.scalars(
        select(SpotterRecord.id)
        .where(SpotterRecord.user_id == user.id)
        .order_by(SpotterRecord.created_at.desc(), SpotterRecord.id.desc())
        .offset(SPOTTER_RECORD_KEEP)
    ).all()
    if stale:
        db.execute(delete(SpotterRecord).where(SpotterRecord.id.in_(stale)))

    db.commit()
    return _state(db, user.id)


class MergeIn(BaseModel):
    """이 브라우저에 쌓여 있던 것. 로그인 직후 한 번만 올라온다."""

    wrong: list[str] = Field(default_factory=list)


@router.post("/state/merge")
def merge_state(
    payload: MergeIn,
    user: CurrentUser = Depends(require_spotter),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """로그인 전에 이 브라우저에 쌓인 오답노트를 계정으로 옮긴다.

    **더하기만 한다.** 로그인 없이 쓰던 사람이 계정을 만들 때 그동안의 오답이
    사라지지 않게 하는 것이 전부다. 빼기까지 하면 기기 하나에 남은 오래된
    목록이 다른 기기에서 맞힌 것을 되살린다.

    기록(`records`)은 안 옮긴다 — 날짜와 점수뿐이라 옮길 값이 크지 않고,
    브라우저마다 다른 시각 표기가 그대로 섞여 들어온다.
    """
    incoming = {q for q in payload.wrong if q}
    if incoming:
        have = set(
            db.scalars(
                select(SpotterWrong.question_id).where(
                    SpotterWrong.user_id == user.id, SpotterWrong.question_id.in_(incoming)
                )
            ).all()
        )
        for qid in incoming - have:
            db.add(SpotterWrong(user_id=user.id, question_id=qid))
        db.commit()
    return _state(db, user.id)
