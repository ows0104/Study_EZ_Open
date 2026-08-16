"""Pre-Quiz 웹 풀이.

**정답은 채점 응답에만 실린다.** 문항을 내려보낼 때 `answer`와 `explanation`을
같이 보내면 개발자 도구로 정답이 보이고, 그러면 `quiz_attempt`에 남는 기록이
아무것도 뜻하지 않게 된다. 채점 결과가 남는 것이 웹 풀이의 존재 이유이므로
채점은 서버에서만 한다.
"""

from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.auth import CurrentUser, get_current_user
from app.database import get_db
from app.models import Asset, PreItem, QuizAttempt
from app.naming import normalize_stem
from app.routes.common import lecture_or_404
from app.storage import ObjectStorage

router = APIRouter()

# `explanation` 첫 줄에 적힌 허용 표기와 그것을 끝맺는 말.
#
#   "Leber hereditary optic neuropathy / LHON / Leber 유전성 시신경병증
#    어느 표기든 정답이다. mtDNA 돌연변이 질환의 원형으로, …"
#
# 끝맺는 말이 줄 끝에 오지 않는다. 실물에서 세 문항 중 두 개가 그 뒤로 해설을
# 이어 쓴다. 그래서 `$`에 붙이지 않고 **표시 앞까지를** 잘라 낸다.
_ALIAS_LINE_RE = re.compile(
    r"^(?P<aliases>.+?)[,\s]*(?:어느\s*)?(?:표기|표현)?\s*(?:든지|든|나|모두|다)?\s*"
    r"정답(?:으로)?\s*(?:인정)?(?:이다|입니다|한다|합니다|된다|됩니다)"
)


def _overlaps(answer: str, candidate: str) -> bool:
    """선언된 정답과 후보가 같은 것을 가리키는가.

    완전일치를 요구할 수 없다. 실물의 `answer`가 `Maternal imprinting(모성 각인)`
    처럼 두 표기를 한데 묶은 형태여서 어느 별칭과도 딱 맞지 않는다. 한쪽이
    다른 쪽에 들어 있으면 같은 것으로 본다.
    """
    if len(candidate) < 2:
        return False
    return candidate in answer or answer in candidate

_OX_ALIASES = {
    "O": {"O", "0", "ㅇ", "○", "◯", "TRUE", "T", "예", "맞다"},
    "X": {"X", "ㅌ", "✕", "×", "FALSE", "F", "아니오", "아니요", "틀리다"},
}


def accepted_answers(item: PreItem) -> set[str]:
    """이 문항이 받아 줄 표기들. 비교용으로 정규화된 형태다.

    단답의 채점은 문자열 완전일치가 아니다. 허용 표기가 `explanation` 첫 줄에
    적혀 있고, 그것을 읽지 않으면 "LHON"이 오답이 된다.

    다만 첫 줄이 늘 별칭 목록인 것은 아니다. 두 가지를 다 만족할 때만 받는다 —
    "…정답이다"라는 표시가 있고, 선언된 `answer`와 겹치는 후보가 하나라도 있을
    것. 아니면 그냥 해설 문장이므로, 무관한 단어를 정답으로 만들어 버리는 것보다
    무시하는 편이 낫다.
    """
    answer = (item.answer or "").strip()
    if item.qtype == "ox":
        key = answer.upper()
        return {normalize_stem(alias) for alias in _OX_ALIASES.get(key, {key})}

    normalized = normalize_stem(answer)
    if item.qtype != "short":
        return {normalized}

    accepted = {normalized}
    match = _ALIAS_LINE_RE.match((item.explanation or "").split("\n", 1)[0].strip())
    if match is None:
        return accepted
    candidates = [
        stem for part in match.group("aliases").split("/") if (stem := normalize_stem(part))
    ]
    if any(_overlaps(normalized, candidate) for candidate in candidates):
        accepted.update(candidates)
    return accepted


def grade(item: PreItem, answered: str) -> bool:
    given = normalize_stem(answered)
    if not given:
        return False
    if item.qtype == "ox":
        given = normalize_stem(answered.strip().upper())
    return given in accepted_answers(item)


def slide_url(db: Session, subject: str, run_id: str, slide_no: int | None) -> str | None:
    """근거 슬라이드. 없으면 None — 오답 해설은 그림 없이도 읽힌다."""
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
    return ObjectStorage().presign_download(asset.object_key)


def missed_items(db: Session, user_id: str, subject: str, run_id: str, limit: int = 3) -> list[dict[str, Any]]:
    """"오늘 놓친 것 N개".

    스킬의 설계 의도가 "틀린 문항이 그 강의의 청취 목표"다. 그래서 순서는
    `must_know` → `core` → `context`이고, 그 안에서는 출제 순서다.
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
    focus_rank = {"must_know": 0, "core": 1, "context": 2}
    rows.sort(key=lambda row: (focus_rank.get(row[0].focus, 3), row[0].ord))
    return [
        {
            "itemId": item.item_id,
            "stem": item.stem,
            "focus": item.focus,
            "retrievalTarget": item.retrieval_target,
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
    user: CurrentUser = Depends(get_current_user),
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
                # `**강조**`는 부정형 발문을 놓치지 말라고 넣은 것이다. 지우지 않는다.
                "stem": item.stem,
                "choices": item.choices,
                "attempt": (
                    {"answered": attempts[item.item_id].answered, "correct": attempts[item.item_id].correct}
                    if item.item_id in attempts
                    else None
                ),
            }
            for item in items
        ],
        "answered": len(attempts),
        "correct": sum(1 for attempt in attempts.values() if attempt.correct),
    }


class GradeRequest(BaseModel):
    item_id: str = Field(alias="itemId")
    answered: str = ""

    model_config = {"populate_by_name": True}


@router.post("/lectures/{subject}/{run_id}/prequiz/grade")
def grade_answer(
    subject: str,
    run_id: str,
    payload: GradeRequest,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    lecture = lecture_or_404(db, subject, run_id)
    item = db.get(PreItem, (lecture.subject, lecture.run_id, payload.item_id))
    if item is None:
        raise HTTPException(status_code=404, detail="문항을 찾을 수 없습니다.")

    correct = grade(item, payload.answered)
    attempt = db.get(QuizAttempt, (user.id, lecture.subject, lecture.run_id, item.item_id))
    if attempt is None:
        attempt = QuizAttempt(
            user_id=user.id, subject=lecture.subject, run_id=lecture.run_id, item_id=item.item_id
        )
        db.add(attempt)
    attempt.answered = payload.answered
    attempt.correct = correct
    db.commit()

    return {
        "itemId": item.item_id,
        "correct": correct,
        "answer": item.answer,
        "explanation": item.explanation,
        "sourceAnchor": item.source_anchor,
        "slideNo": item.slide_no,
        "slideUrl": slide_url(db, lecture.subject, lecture.run_id, item.slide_no),
    }


@router.delete("/lectures/{subject}/{run_id}/prequiz/attempts", status_code=204)
def reset_attempts(
    subject: str,
    run_id: str,
    user: CurrentUser = Depends(get_current_user),
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
