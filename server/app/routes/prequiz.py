"""Pre-Quiz 웹 풀이.

배급의 기본은 apkg다. 이 화면은 그 옆에 있는 갈래다 — Anki를 안 깐 자리에서,
받아 가기 전에 한 번 훑어보는 자리.

## 채점을 서버가 하지 않는다

한동안 5지선다·단답이었고 서버가 문자열로 채점했다. 파이프라인이 pdf2anki로
갈리면서 카드가 **Anki와 같은 앞면/뒷면**이 되었다 — 답이 한 줄짜리 낱말일 때도
있지만 대개는 여러 줄 산문이다. 그걸 문자열 완전일치로 재면 전원이 틀리고,
별칭 목록을 파싱해 봐야 「거의 맞았다」를 가르지 못한다.

그래서 순서를 뒤집었다.

    문항을 받는다 (답 없이)  →  답을 편다 (reveal)  →  본인이 맞았다/틀렸다를 찍는다

`quiz_attempt.correct`는 그래서 **서버의 판정이 아니라 본인의 판정**이다.
Anki가 하는 것과 같은 방식이고, 이 덱이 실제로 쓰이는 방식이기도 하다.

**그래도 답은 문항과 함께 안 내려보낸다.** 같이 보내면 펴 보지 않고도 정답이
보이고, 그러면 「맞았다」가 아무것도 뜻하지 않는다. 답을 받아 가는 자리가
따로 있어야 그 기록이 무언가를 말한다.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.auth import CurrentUser, require_approved_user
from app.database import get_db
from app.models import Asset, PreItem, QuizAttempt
from app.routes.common import lecture_or_404
from app.storage import ObjectStorage, StorageNotConfigured

router = APIRouter()


def slide_url(db: Session, subject: str, run_id: str, slide_no: int | None) -> str | None:
    """근거 슬라이드. 없으면 None — 해설은 그림 없이도 읽힌다."""
    if slide_no is None:
        return None
    asset = db.scalar(
        select(Asset).where(
            Asset.subject == subject,
            Asset.run_id == run_id,
            Asset.kind == "media",
            Asset.slide_no == slide_no,
        )
    )
    if asset is None:
        return None
    try:
        return ObjectStorage().presign_download(asset.object_key)
    except StorageNotConfigured:
        # 해설은 그림 없이도 읽힌다. 화면 전체를 막을 이유가 없다.
        return None


def missed_items(db: Session, user_id: str, subject: str, run_id: str, limit: int = 3) -> list[dict[str, Any]]:
    """"오늘 놓친 것 N개". 웹에서 푼 사람에게만 나온다.

    틀린 카드가 그 강의에서 특히 귀 기울일 곳이라는 생각으로 고른다. 그래서
    순서는 `focus`가 뼈대·용어인 것부터이고, 그 안에서는 출제 순서다.
    """
    rows = db.execute(
        select(PreItem, QuizAttempt)
        .join(
            QuizAttempt,
            (QuizAttempt.subject == PreItem.subject)
            & (QuizAttempt.run_id == PreItem.run_id)
            & (QuizAttempt.item_id == PreItem.item_id)
            & (QuizAttempt.user_id == user_id),
        )
        .where(PreItem.subject == subject, PreItem.run_id == run_id, QuizAttempt.correct.is_(False))
    ).all()
    # 예습 카드는 등급이 없다(전부 「꼭 반드시」다). 대신 **왜 그런가**로 세운다 —
    # 뼈대와 용어를 모르면 그 뒤가 통째로 안 붙는다.
    focus_rank = {"spine": 0, "vocabulary": 1, "mechanism": 2, "clinical": 3, "repeated": 4}
    rows.sort(key=lambda row: (focus_rank.get(row[0].focus, 9), row[0].ord))
    return [
        {
            "itemId": item.item_id,
            "stem": item.stem,
            "answer": item.answer,
            "focus": item.focus,
            "cardType": item.card_type,
            "explanation": item.explanation,
            "slideNo": item.slide_no,
            "examHit": item.exam_hit,
        }
        for item, _ in rows[:limit]
    ]


@router.get("/lectures/{subject}/{run_id}/prequiz")
def read_prequiz(
    subject: str,
    run_id: str,
    user: CurrentUser = Depends(require_approved_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    lecture = lecture_or_404(db, subject, run_id)
    items = db.scalars(
        select(PreItem)
        .where(PreItem.subject == lecture.subject, PreItem.run_id == lecture.run_id)
        .order_by(PreItem.ord)
    ).all()
    attempts = {
        attempt.item_id: attempt
        for attempt in db.scalars(
            select(QuizAttempt).where(
                QuizAttempt.user_id == user.id,
                QuizAttempt.subject == lecture.subject,
                QuizAttempt.run_id == lecture.run_id,
            )
        )
    }
    return {
        "subject": lecture.subject,
        "runId": lecture.run_id,
        "title": lecture.title,
        "items": [
            {
                "itemId": item.item_id,
                "qtype": item.qtype,
                "stem": item.stem,
                "focus": item.focus,
                "cardType": item.card_type,
                "examHit": item.exam_hit,
                # `answer`·`explanation`은 여기 없다. `reveal`이 준다.
                "attempt": (
                    {"correct": attempts[item.item_id].correct}
                    if item.item_id in attempts
                    else None
                ),
            }
            for item in items
        ],
        "answered": len(attempts),
        "correct": sum(1 for attempt in attempts.values() if attempt.correct),
    }


class ItemRef(BaseModel):
    item_id: str = Field(alias="itemId")

    model_config = {"populate_by_name": True}


class GradeRequest(ItemRef):
    """`correct`는 **본인이 찍은 것**이다. 서버는 받아 적기만 한다."""

    correct: bool = False


def _item_or_404(db: Session, subject: str, run_id: str, item_id: str) -> PreItem:
    lecture = lecture_or_404(db, subject, run_id)
    item = db.get(PreItem, (lecture.subject, lecture.run_id, item_id))
    if item is None:
        raise HTTPException(status_code=404, detail="문항을 찾을 수 없습니다.")
    return item


@router.post("/lectures/{subject}/{run_id}/prequiz/reveal")
def reveal_answer(
    subject: str,
    run_id: str,
    payload: ItemRef,
    user: CurrentUser = Depends(require_approved_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """답을 편다. **아무것도 기록하지 않는다.**

    폈다는 것만으로 「풀었다」로 세면 답을 보고 넘긴 카드까지 기록에 섞인다.
    기록은 본인이 맞았다/틀렸다를 찍을 때(`grade`) 남는다.
    """
    item = _item_or_404(db, subject, run_id, payload.item_id)
    return {
        "itemId": item.item_id,
        "answer": item.answer,
        "explanation": item.explanation,
        "sourceAnchor": item.source_anchor,
        "slideNo": item.slide_no,
        "slideUrl": slide_url(db, item.subject, item.run_id, item.slide_no),
    }


@router.post("/lectures/{subject}/{run_id}/prequiz/grade")
def grade_answer(
    subject: str,
    run_id: str,
    payload: GradeRequest,
    user: CurrentUser = Depends(require_approved_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    item = _item_or_404(db, subject, run_id, payload.item_id)
    attempt = db.get(QuizAttempt, (user.id, item.subject, item.run_id, item.item_id))
    if attempt is None:
        attempt = QuizAttempt(
            user_id=user.id, subject=item.subject, run_id=item.run_id, item_id=item.item_id
        )
        db.add(attempt)
    attempt.correct = payload.correct
    db.commit()
    return {"itemId": item.item_id, "correct": attempt.correct}


@router.delete("/lectures/{subject}/{run_id}/prequiz/attempts", status_code=204)
def reset_attempts(
    subject: str,
    run_id: str,
    user: CurrentUser = Depends(require_approved_user),
    db: Session = Depends(get_db),
) -> None:
    lecture = lecture_or_404(db, subject, run_id)
    db.execute(
        delete(QuizAttempt).where(
            QuizAttempt.user_id == user.id,
            QuizAttempt.subject == lecture.subject,
            QuizAttempt.run_id == lecture.run_id,
        )
    )
    db.commit()
