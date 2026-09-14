"""웹 풀이. **예습과 복습 두 갈래가 이 한 파일을 쓴다.**

**웹 풀이가 기본이다**(2026-08-23 관리자 지시). 화면에서 Pre-Quiz를 누르면 전용
창에 이 문항들이 뜨고, apkg는 그 옆의 내려받기 버튼으로 내려갔다. 강의 직전 한
번 훑는 것이 예습 덱의 쓰임이라 여는 데 Anki가 끼지 않는 편이 낫고, 반복해서
돌릴 사람은 덱을 받아 간다.

복습도 2026-08-31에 같은 자리를 얻었다(관리자 지시). 다른 것은 표 셋뿐이라
(`Quiz`) 화면도 규칙도 그대로 쓴다. **다만 복습 덱은 Anki에서 3패스로 돌고 그
진행은 Anki가 든다** — 여기 쌓이는 것은 웹에서 푼 몫뿐이라, 둘을 더해 「몇 번
봤다」로 읽으면 안 된다.

## 채점을 서버가 하지 않는다

한동안 5지선다·단답이었고 서버가 문자열로 채점했다. 파이프라인이 pdf2anki(지금의 `quizgen/`)로
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

from typing import Any, NamedTuple

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.auth import CurrentUser, require_approved_user
from app.database import get_db
from app.models import SLIDE_KINDS, Asset, MainAttempt, MainItem, PreItem, QuizAttempt
from app.routes.common import lecture_or_404
from app.storage import ObjectStorage, StorageNotConfigured

router = APIRouter()


class Quiz(NamedTuple):
    """한 갈래가 쓰는 표 셋. 라우트는 이것만 골라 넘긴다.

    **표가 갈린 이유는 `item_id`가 겹치기 때문이다** — 두 갈래 다 `c001`부터
    센다. 자세한 것은 `app/models.py`의 `_QuizItem`에 있다.
    """

    name: str
    item: type
    attempt: type
    #: 근거 슬라이드가 어느 asset kind로 올라와 있나. **갈라 두지 않으면
    #: 같은 `slide_no`가 둘이 되고 아래 `db.scalar`가 아무거나 집는다.**
    slides: str


PRE = Quiz("pre", PreItem, QuizAttempt, SLIDE_KINDS["pre"])
MAIN = Quiz("main", MainItem, MainAttempt, SLIDE_KINDS["main"])


def slide_url(
    db: Session, subject: str, run_id: str, slide_no: int | None, quiz: Quiz = PRE
) -> str | None:
    """근거 슬라이드. 없으면 None — 해설은 그림 없이도 읽힌다."""
    if slide_no is None:
        return None
    asset = db.scalar(
        select(Asset).where(
            Asset.subject == subject,
            Asset.run_id == run_id,
            Asset.kind == quiz.slides,
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


def missed_items(
    db: Session, user_id: str, subject: str, run_id: str, limit: int = 3, quiz: Quiz = PRE
) -> list[dict[str, Any]]:
    """"오늘 놓친 것 N개". 웹에서 푼 사람에게만 나온다.

    틀린 카드가 그 강의에서 특히 귀 기울일 곳이라는 생각으로 고른다. 그래서
    순서는 `focus`가 뼈대·용어인 것부터이고, 그 안에서는 출제 순서다.
    """
    item, attempt = quiz.item, quiz.attempt
    rows = db.execute(
        select(item, attempt)
        .join(
            attempt,
            (attempt.subject == item.subject)
            & (attempt.run_id == item.run_id)
            & (attempt.item_id == item.item_id)
            & (attempt.user_id == user_id),
        )
        .where(item.subject == subject, item.run_id == run_id, attempt.correct.is_(False))
    ).all()
    # 예습 카드는 등급이 없다(전부 「꼭 반드시」다). 대신 **왜 그런가**로 세운다 —
    # 뼈대와 용어를 모르면 그 뒤가 통째로 안 붙는다. 복습 카드의 `focus`는 등급이라
    # 이 표에 안 걸리고, 그러면 출제 순서로만 선다 — 그것으로 족하다.
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


def _read(quiz: Quiz, db: Session, user_id: str, subject: str, run_id: str) -> dict[str, Any]:
    lecture = lecture_or_404(db, subject, run_id)
    item, attempt = quiz.item, quiz.attempt
    items = db.scalars(
        select(item)
        .where(item.subject == lecture.subject, item.run_id == lecture.run_id)
        .order_by(item.ord)
    ).all()
    attempts = {
        row.item_id: row
        for row in db.scalars(
            select(attempt).where(
                attempt.user_id == user_id,
                attempt.subject == lecture.subject,
                attempt.run_id == lecture.run_id,
            )
        )
    }
    return {
        "subject": lecture.subject,
        "runId": lecture.run_id,
        "title": lecture.title,
        "kind": quiz.name,
        "items": [
            {
                "itemId": row.item_id,
                "qtype": row.qtype,
                "stem": row.stem,
                "focus": row.focus,
                "cardType": row.card_type,
                "examHit": row.exam_hit,
                # `answer`·`explanation`은 여기 없다. `reveal`이 준다.
                "attempt": (
                    {"correct": attempts[row.item_id].correct}
                    if row.item_id in attempts
                    else None
                ),
            }
            for row in items
        ],
        "answered": len(attempts),
        "correct": sum(1 for row in attempts.values() if row.correct),
    }


class ItemRef(BaseModel):
    item_id: str = Field(alias="itemId")

    model_config = {"populate_by_name": True}


class GradeRequest(ItemRef):
    """`correct`는 **본인이 찍은 것**이다. 서버는 받아 적기만 한다."""

    correct: bool = False


def _item_or_404(quiz: Quiz, db: Session, subject: str, run_id: str, item_id: str):
    lecture = lecture_or_404(db, subject, run_id)
    item = db.get(quiz.item, (lecture.subject, lecture.run_id, item_id))
    if item is None:
        raise HTTPException(status_code=404, detail="문항을 찾을 수 없습니다.")
    return item


def _reveal(quiz: Quiz, db: Session, subject: str, run_id: str, item_id: str) -> dict[str, Any]:
    """답을 편다. **아무것도 기록하지 않는다.**

    폈다는 것만으로 「풀었다」로 세면 답을 보고 넘긴 카드까지 기록에 섞인다.
    기록은 본인이 맞았다/틀렸다를 찍을 때(`grade`) 남는다.
    """
    item = _item_or_404(quiz, db, subject, run_id, item_id)
    return {
        "itemId": item.item_id,
        "answer": item.answer,
        "explanation": item.explanation,
        "sourceAnchor": item.source_anchor,
        "slideNo": item.slide_no,
        "slideUrl": slide_url(db, item.subject, item.run_id, item.slide_no, quiz),
    }


def _grade(
    quiz: Quiz, db: Session, user_id: str, subject: str, run_id: str, payload: GradeRequest
) -> dict[str, Any]:
    item = _item_or_404(quiz, db, subject, run_id, payload.item_id)
    attempt = db.get(quiz.attempt, (user_id, item.subject, item.run_id, item.item_id))
    if attempt is None:
        attempt = quiz.attempt(
            user_id=user_id, subject=item.subject, run_id=item.run_id, item_id=item.item_id
        )
        db.add(attempt)
    attempt.correct = payload.correct
    db.commit()
    return {"itemId": item.item_id, "correct": attempt.correct}


def _reset(quiz: Quiz, db: Session, user_id: str, subject: str, run_id: str) -> None:
    lecture = lecture_or_404(db, subject, run_id)
    attempt = quiz.attempt
    db.execute(
        delete(attempt).where(
            attempt.user_id == user_id,
            attempt.subject == lecture.subject,
            attempt.run_id == lecture.run_id,
        )
    )
    db.commit()


# ---------------------------------------------------------------- 예습 (Pre-Quiz)


@router.get("/lectures/{subject}/{run_id}/prequiz")
def read_prequiz(
    subject: str,
    run_id: str,
    user: CurrentUser = Depends(require_approved_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return _read(PRE, db, user.id, subject, run_id)


@router.post("/lectures/{subject}/{run_id}/prequiz/reveal")
def reveal_answer(
    subject: str,
    run_id: str,
    payload: ItemRef,
    user: CurrentUser = Depends(require_approved_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return _reveal(PRE, db, subject, run_id, payload.item_id)


@router.post("/lectures/{subject}/{run_id}/prequiz/grade")
def grade_answer(
    subject: str,
    run_id: str,
    payload: GradeRequest,
    user: CurrentUser = Depends(require_approved_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return _grade(PRE, db, user.id, subject, run_id, payload)


@router.delete("/lectures/{subject}/{run_id}/prequiz/attempts", status_code=204)
def reset_attempts(
    subject: str,
    run_id: str,
    user: CurrentUser = Depends(require_approved_user),
    db: Session = Depends(get_db),
) -> None:
    _reset(PRE, db, user.id, subject, run_id)


# ---------------------------------------------------------------- 복습 (Main-Quiz)
#
# 경로를 `/prequiz?kind=main`으로 겹치지 않고 따로 낸 이유는, 예습 쪽이 이미
# 나가 있는 계약이기 때문이다. 갈래를 질의로 받으면 기본값이 생기고, 기본값이
# 있는 자리는 언젠가 잘못 온 요청을 조용히 예습으로 처리한다.


@router.get("/lectures/{subject}/{run_id}/mainquiz")
def read_mainquiz(
    subject: str,
    run_id: str,
    user: CurrentUser = Depends(require_approved_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return _read(MAIN, db, user.id, subject, run_id)


@router.post("/lectures/{subject}/{run_id}/mainquiz/reveal")
def reveal_main_answer(
    subject: str,
    run_id: str,
    payload: ItemRef,
    user: CurrentUser = Depends(require_approved_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return _reveal(MAIN, db, subject, run_id, payload.item_id)


@router.post("/lectures/{subject}/{run_id}/mainquiz/grade")
def grade_main_answer(
    subject: str,
    run_id: str,
    payload: GradeRequest,
    user: CurrentUser = Depends(require_approved_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return _grade(MAIN, db, user.id, subject, run_id, payload)


@router.delete("/lectures/{subject}/{run_id}/mainquiz/attempts", status_code=204)
def reset_main_attempts(
    subject: str,
    run_id: str,
    user: CurrentUser = Depends(require_approved_user),
    db: Session = Depends(get_db),
) -> None:
    _reset(MAIN, db, user.id, subject, run_id)
