"""웹 풀이. **예습과 복습 두 갈래가 이 한 파일을 쓴다.**

**웹 풀이가 기본이다**(2026-08-23 관리자 지시). 화면에서 Pre-Quiz를 누르면 전용
창에 이 문항들이 뜨고, apkg는 그 옆의 내려받기 버튼으로 내려갔다. 강의 직전 한
번 훑는 것이 예습 덱의 쓰임이라 여는 데 Anki가 끼지 않는 편이 낫고, 반복해서
돌릴 사람은 덱을 받아 간다.

복습도 2026-08-31에 같은 자리를 얻었다(관리자 지시). 다른 것은 표 셋뿐이라
(`Quiz`) 화면도 규칙도 그대로 쓴다. **다만 복습 덱은 Anki에서 3패스로 돌고 그
진행은 Anki가 든다** — 여기 쌓이는 것은 웹에서 푼 몫뿐이라, 둘을 더해 「몇 번
봤다」로 읽으면 안 된다.

## 반복은 이제 여기서 돈다

**2026-09-18 관리자 지시** — 「웹 퀴즈를 안키처럼 해줘. 망각곡선에 기반해서.
그리고 이전으로 돌아가는 기능도 만들어줘.」

그 전까지 웹은 **한 번 훑는 자리**였다. 카드마다 `correct` 불리언 하나가 남고,
반복은 apkg를 받아 간 사람의 안키가 들었다. 지금은 카드마다 일정이 있다.

    찍는다  →  `app/srs.py`(안키의 SM-2)가 다음 때를 정한다  →  그 때가 되면 다시 나온다

**일정을 정하는 곳은 `app/srs.py` 하나다.** 이 파일은 그것을 표에 옮겨 적고,
화면은 서버가 준 값을 그대로 읽는다 — 어느 쪽도 간격을 자기 계산으로 정하지
않는다. 그래서 `reveal`이 네 버튼의 결과(`next`)까지 같이 보낸다.

**`grade`는 넷이다**(again·hard·good·easy). 옛 화면이 보내던 `{correct: bool}`도
계속 받는다 — 이 저장소는 **API를 먼저 배포하고 프론트를 나중에 민다**
(`../CLAUDE.md`). 그 사이에 열려 있는 탭이 보내는 것이 옛 꼴이다.

## 되돌리기는 계산이 아니라 기억이다

SM-2는 한쪽으로만 간다. 간격을 쉬움도로 나눠 봐야 반올림한 자리가 안 돌아오고,
잊어서 하루로 깎인 카드는 깎기 전 간격이 아예 사라진다. 그래서 찍을 때마다
**찍기 전의 일곱 값을 그대로** 적어 두고(`_ReviewLog`), 되돌리기는 마지막 줄을
뽑아 되쓴다. 안키의 undo와 같은 방식이다.

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

from datetime import UTC, datetime
from typing import Any, NamedTuple

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app import srs
from app.auth import CurrentUser, require_approved_user
from app.database import get_db
from app.models import (
    SLIDE_KINDS,
    Asset,
    MainAttempt,
    MainItem,
    MainReviewLog,
    PreItem,
    PreReviewLog,
    QuizAttempt,
)
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
    #: 되돌리기 기록. 갈래마다 따로인 이유는 위와 같다.
    log: type


PRE = Quiz("pre", PreItem, QuizAttempt, SLIDE_KINDS["pre"], PreReviewLog)
MAIN = Quiz("main", MainItem, MainAttempt, SLIDE_KINDS["main"], MainReviewLog)


# ---------------------------------------------------------------- 일정 ↔ 표
#
# `srs.Card`와 표의 칼럼은 이름까지 같다. 그래도 옮겨 적는 함수를 두는 이유는,
# **옛 줄에는 일정 칼럼이 없기 때문이다** — 값이 `None`으로 올라오는 자리를
# 한 곳에서만 메워야 한다.


def _card(attempt: Any | None) -> srs.Card:
    """표의 한 줄을 일정이 보는 카드로. 줄이 없으면 새 카드다."""
    if attempt is None:
        return srs.Card()
    return srs.Card(
        state=attempt.state or srs.STATE_NEW,
        step=attempt.step or 0,
        interval_days=attempt.interval_days or 0,
        ease=attempt.ease or srs.STARTING_EASE,
        reps=attempt.reps or 0,
        lapses=attempt.lapses or 0,
        due_at=attempt.due_at,
    )


def _as_utc(when: datetime | None) -> datetime | None:
    """SQLite는 시간대를 안 싣고 돌려준다. 비교하기 전에 여기서 붙인다."""
    if when is None:
        return None
    return when if when.tzinfo else when.replace(tzinfo=UTC)


def _schedule(attempt: Any) -> dict[str, Any]:
    """화면이 큐를 세울 때 필요한 전부.

    **줄이 없는 카드는 `null`로 내려간다**(`attempt: null`). 그것이 이미 나가
    있는 계약이고, 옛 화면은 그 `null`로 「어디부터 이어서 풀까」를 정한다.
    새 화면은 `null`을 새 카드로 읽는다 — 새 카드의 기본값은 「지금 낸다」라서
    일정을 계산할 일이 없다.

    `correct`가 맨 앞에 남아 있는 것도 그 계약이다. 넷 중 `again`이면 거짓이다.
    """
    card = _card(attempt)
    due_at = _as_utc(card.due_at)
    return {
        "correct": bool(attempt.correct),
        "state": card.state,
        "step": card.step,
        "intervalDays": card.interval_days,
        "ease": round(card.ease, 2),
        "reps": card.reps,
        "lapses": card.lapses,
        "dueAt": due_at.isoformat() if due_at else None,
    }


def _write_card(attempt: Any, card: srs.Card) -> None:
    attempt.state = card.state
    attempt.step = card.step
    attempt.interval_days = card.interval_days
    attempt.ease = card.ease
    attempt.reps = card.reps
    attempt.lapses = card.lapses
    attempt.due_at = card.due_at


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

    ## 2026-09-18에 재료를 바꿨다 — 그 전 방식으로는 **영영 비게 된다**

    전에는 `attempt.correct`가 거짓인 줄을 골랐다. 일정이 생긴 뒤에는 그 값이
    거짓인 카드가 **언제나 큐에 남아 있다** — Again은 분 단위로 다시 내고, 큐는
    남은 것이 그것뿐일 때 때가 안 됐어도 미리 낸다. 그래서 「다 했다」에 닿는
    순간에는 거짓인 줄이 하나도 없고 목록은 늘 0개다.

    지금은 **오늘 Again을 누른 카드**를 고른다(`_ReviewLog`). 뒤에 다시 맞혔는지는
    안 본다 — 「오늘 한 번 막혔다」가 강의에서 귀를 세울 자리라는 원래 생각에
    오히려 가깝다.

    하루의 경계는 복습이 쓰는 그것이다(`srs.day_start` · 한국 시각 새벽 4시).
    **다음 날 이 화면을 열면 비어 있다** — 제목이 「오늘」이라고 적고 있으므로
    그것이 맞다.
    """
    item, log = quiz.item, quiz.log
    missed_ids = set(
        db.scalars(
            select(log.item_id).where(
                log.user_id == user_id,
                log.subject == subject,
                log.run_id == run_id,
                log.grade == "again",
                log.reviewed_at >= srs.day_start(datetime.now(UTC)),
            )
        ).all()
    )
    if not missed_ids:
        return []
    rows = list(
        db.scalars(
            select(item).where(
                item.subject == subject,
                item.run_id == run_id,
                item.item_id.in_(missed_ids),
            )
        ).all()
    )
    # 예습 카드는 등급이 없다(전부 「꼭 반드시」다). 대신 **왜 그런가**로 세운다 —
    # 뼈대와 용어를 모르면 그 뒤가 통째로 안 붙는다. 복습 카드의 `focus`는 등급이라
    # 이 표에 안 걸리고, 그러면 출제 순서로만 선다 — 그것으로 족하다.
    focus_rank = {"spine": 0, "vocabulary": 1, "mechanism": 2, "clinical": 3, "repeated": 4}
    rows.sort(key=lambda row: (focus_rank.get(row.focus, 9), row.ord))
    return [
        {
            "itemId": row.item_id,
            "stem": row.stem,
            "answer": row.answer,
            "focus": row.focus,
            "cardType": row.card_type,
            "explanation": row.explanation,
            "slideNo": row.slide_no,
            "examHit": row.exam_hit,
        }
        for row in rows[:limit]
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
                # 왜 냈나 · 도전 문제인가. 답이 아니라서 앞면과 같이 준다.
                "whyAsked": row.why_asked,
                "challenge": row.challenge,
                "whyTags": list(row.why_tags or []),
                # `answer`·`explanation`은 여기 없다. `reveal`이 준다.
                "attempt": (
                    _schedule(attempts[row.item_id]) if row.item_id in attempts else None
                ),
            }
            for row in items
        ],
        "answered": len(attempts),
        "correct": sum(1 for row in attempts.values() if row.correct),
        # **화면의 시계를 믿지 않는다.** 익히는 단계는 분 단위라, 기계 시각이
        # 몇 분 틀어져 있으면 「1분 뒤」가 이미 지난 일이 되거나 영영 안 온다.
        # 화면은 이 값으로 차이를 재서 자기 시계를 보정한다.
        "now": datetime.now(UTC).isoformat(),
        # 되돌릴 것이 있는가. 없으면 화면이 버튼을 아예 안 켠다 — 눌러 보고
        # 404를 받는 것으로 알게 하면 안 된다.
        "undoable": _undo_depth(quiz, db, user_id, lecture.subject, lecture.run_id) > 0,
    }


def _undo_depth(quiz: Quiz, db: Session, user_id: str, subject: str, run_id: str) -> int:
    log = quiz.log
    return int(
        db.scalar(
            select(func.count())
            .select_from(log)
            .where(log.user_id == user_id, log.subject == subject, log.run_id == run_id)
        )
        or 0
    )


def due_counts(
    db: Session, user_id: str, subject: str, run_id: str, quiz: Quiz, now: datetime | None = None
) -> dict[str, Any]:
    """이 사람이 이 편에서 **지금 낼 카드가 몇 장인가.**

    강의 상세와 캘린더가 쓴다 — 그쪽은 문항 목록을 안 받으므로 직접 셀 수 없다.
    푸는 창은 목록을 받으니 자기가 센다(같은 셈을 두 번 적지 않으려고 여기서
    목록을 안 만든다).

    **0을 갈라서 센다.** 재료가 없어서 0인 것과, 다 익어서 아직 때가 아닌 0과,
    오늘 몫을 끝낸 0이 화면에서 같은 0으로 보이면 사람은 「고장」으로 읽는다
    (`../CLAUDE.md` 함정 ③).
    """
    now = now or datetime.now(UTC)
    item, attempt = quiz.item, quiz.attempt
    rows = db.execute(
        select(item.item_id, attempt)
        .outerjoin(
            attempt,
            (attempt.subject == item.subject)
            & (attempt.run_id == item.run_id)
            & (attempt.item_id == item.item_id)
            & (attempt.user_id == user_id),
        )
        .where(item.subject == subject, item.run_id == run_id)
    ).all()

    counts = {"new": 0, "learning": 0, "review": 0, "later": 0}
    next_due: datetime | None = None
    for _, row in rows:
        card = _card(row)
        if row is None or card.state == srs.STATE_NEW:
            counts["new"] += 1
            continue
        if card.state != srs.STATE_REVIEW:
            # 익히는 중인 카드는 때를 안 본다. **오늘 안에 나온다** — 분 단위로
            # 잡힌 카드를 화면이 미리 내기 때문이다(`web/src/lecture/queue.ts`).
            # 때를 보고 「나중」으로 세면 「오늘 낼 것 0」이라고 적으면서 카드를
            # 내밀게 된다.
            counts["learning"] += 1
            continue
        due = _as_utc(card.due_at)
        if due is None or due <= now:
            counts["review"] += 1
            continue
        counts["later"] += 1
        if next_due is None or due < next_due:
            next_due = due
    return {
        **counts,
        "due": counts["new"] + counts["learning"] + counts["review"],
        "nextDueAt": next_due.isoformat() if next_due else None,
    }


class ItemRef(BaseModel):
    item_id: str = Field(alias="itemId")

    model_config = {"populate_by_name": True}


class GradeRequest(ItemRef):
    """무엇을 눌렀나. **판정하는 것은 본인이고 서버는 받아 적는다.**

    `grade`가 넷(again·hard·good·easy)이고, 없으면 옛 꼴(`correct`)로 읽는다.
    옛 꼴을 계속 받는 이유는 배포 순서다 — 이 저장소는 API를 먼저 올리고
    프론트를 나중에 미니까, 그 사이에 열려 있는 탭은 `{correct: bool}`을 보낸다.
    옛 화면에는 Again과 Pass 둘뿐이었으므로 Pass는 `good`으로 받는다.
    """

    grade: str | None = None
    correct: bool | None = None

    def resolved(self) -> str:
        if self.grade is not None:
            if self.grade not in srs.GRADES:
                joined = ", ".join(srs.GRADES)
                raise HTTPException(status_code=422, detail=f"채점은 {joined} 중 하나입니다.")
            return self.grade
        if self.correct is not None:
            return "good" if self.correct else "again"
        raise HTTPException(status_code=422, detail="무엇을 눌렀는지가 없습니다.")


def _item_or_404(quiz: Quiz, db: Session, subject: str, run_id: str, item_id: str):
    lecture = lecture_or_404(db, subject, run_id)
    item = db.get(quiz.item, (lecture.subject, lecture.run_id, item_id))
    if item is None:
        raise HTTPException(status_code=404, detail="문항을 찾을 수 없습니다.")
    return item


def _reveal(
    quiz: Quiz, db: Session, user_id: str, subject: str, run_id: str, item_id: str
) -> dict[str, Any]:
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
        # **버튼에 적을 「언제 다시 나오나」를 서버가 잰다.** 화면이 자기
        # 계산으로 적으면 사다리가 파이썬과 타입스크립트 두 곳에 산다.
        # 여기서도 아무것도 저장하지 않는다 — `srs.preview`는 순수 함수다.
        "next": srs.preview(_card(_attempt_row(quiz, db, user_id, item)), datetime.now(UTC)),
    }


def _attempt_row(quiz: Quiz, db: Session, user_id: str, item: Any) -> Any | None:
    return db.get(quiz.attempt, (user_id, item.subject, item.run_id, item.item_id))


def _grade(
    quiz: Quiz, db: Session, user_id: str, subject: str, run_id: str, payload: GradeRequest
) -> dict[str, Any]:
    """찍은 것을 받아 적고 다음 때를 정한다.

    순서가 중요하다. **되돌릴 값을 먼저 적고 나서 일정을 민다** — 반대로 하면
    적어 둘 「찍기 전」이 이미 없다.
    """
    grade = payload.resolved()
    item = _item_or_404(quiz, db, subject, run_id, payload.item_id)
    now = datetime.now(UTC)

    attempt = _attempt_row(quiz, db, user_id, item)
    before = _card(attempt)
    db.add(
        quiz.log(
            user_id=user_id,
            subject=item.subject,
            run_id=item.run_id,
            item_id=item.item_id,
            grade=grade,
            reviewed_at=now,
            # 줄이 없었다면 이 찍기가 줄을 만든 것이다. 되돌릴 때는 값을
            # 되쓰는 것으로 안 되고 줄을 지워야 한다 - 안 그러면 「몇 장
            # 봤다」가 안 본 카드를 센다.
            had_attempt=attempt is not None,
            prev_correct=bool(attempt.correct) if attempt is not None else False,
            prev_state=before.state,
            prev_step=before.step,
            prev_interval_days=before.interval_days,
            prev_ease=before.ease,
            prev_reps=before.reps,
            prev_lapses=before.lapses,
            prev_due_at=before.due_at,
        )
    )

    if attempt is None:
        attempt = quiz.attempt(
            user_id=user_id, subject=item.subject, run_id=item.run_id, item_id=item.item_id
        )
        db.add(attempt)
    # `correct`는 남는다. 「오늘 놓친 것」과 진행 수가 이 값으로 서 있다.
    attempt.correct = grade != "again"
    attempt.answered_at = now
    _write_card(attempt, srs.review(before, grade, now))
    db.commit()
    return {
        "itemId": item.item_id,
        "grade": grade,
        "correct": attempt.correct,
        "attempt": _schedule(attempt),
        "now": now.isoformat(),
        "undoable": True,
    }


def _undo(quiz: Quiz, db: Session, user_id: str, subject: str, run_id: str) -> dict[str, Any]:
    """마지막으로 찍은 것을 되돌린다. **한 번에 한 장이고, 몇 번이든 된다.**

    안키의 undo와 같은 자리다. 되돌린 카드는 답이 펴진 채로 다시 서므로,
    답 화면에 필요한 것(`_reveal`)을 같이 실어 보낸다 — 되돌리자마자 화면이
    `reveal`을 한 번 더 부르게 두면 누른 뒤에 빈 화면이 한 박자 보인다.

    **기록은 한 세션 안에만 있는 것이 아니다.** 표에 남으므로 어제 찍은 것도
    되돌려진다. 안키는 세션 안에서만 되돌리는데, 웹에서 그렇게 하려면
    「세션」이 무엇인지 먼저 정해야 한다 — 탭을 닫아도 서버에는 남고, 그
    경계는 사람이 느끼는 경계와 다르다.
    """
    log = quiz.log
    row = db.scalars(
        select(log)
        .where(log.user_id == user_id, log.subject == subject, log.run_id == run_id)
        .order_by(log.id.desc())
        .limit(1)
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="되돌릴 것이 없습니다.")

    attempt = db.get(quiz.attempt, (user_id, row.subject, row.run_id, row.item_id))
    if not row.had_attempt:
        if attempt is not None:
            db.delete(attempt)
        attempt = None
    elif attempt is not None:
        attempt.correct = row.prev_correct
        _write_card(
            attempt,
            srs.Card(
                state=row.prev_state,
                step=row.prev_step,
                interval_days=row.prev_interval_days,
                ease=row.prev_ease,
                reps=row.prev_reps,
                lapses=row.prev_lapses,
                due_at=row.prev_due_at,
            ),
        )
    item_id = row.item_id
    db.delete(row)
    db.commit()

    revealed = _reveal(quiz, db, user_id, subject, run_id, item_id)
    return {
        **revealed,
        "attempt": _schedule(attempt) if attempt is not None else None,
        "now": datetime.now(UTC).isoformat(),
        "undoable": _undo_depth(quiz, db, user_id, subject, run_id) > 0,
    }


def _reset(quiz: Quiz, db: Session, user_id: str, subject: str, run_id: str) -> None:
    """이 편의 일정을 통째로 버린다. 전부 새 카드가 된다.

    **되돌리기 기록도 같이 지운다.** 남겨 두면 없는 줄을 되살리려는 되돌리기가
    남고, 그 되돌리기는 지워진 일정을 일부만 되돌려 놓는다.
    """
    lecture = lecture_or_404(db, subject, run_id)
    for table in (quiz.attempt, quiz.log):
        db.execute(
            delete(table).where(
                table.user_id == user_id,
                table.subject == lecture.subject,
                table.run_id == lecture.run_id,
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
    return _reveal(PRE, db, user.id, subject, run_id, payload.item_id)


@router.post("/lectures/{subject}/{run_id}/prequiz/grade")
def grade_answer(
    subject: str,
    run_id: str,
    payload: GradeRequest,
    user: CurrentUser = Depends(require_approved_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return _grade(PRE, db, user.id, subject, run_id, payload)


@router.post("/lectures/{subject}/{run_id}/prequiz/undo")
def undo_answer(
    subject: str,
    run_id: str,
    user: CurrentUser = Depends(require_approved_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return _undo(PRE, db, user.id, subject, run_id)


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
    return _reveal(MAIN, db, user.id, subject, run_id, payload.item_id)


@router.post("/lectures/{subject}/{run_id}/mainquiz/grade")
def grade_main_answer(
    subject: str,
    run_id: str,
    payload: GradeRequest,
    user: CurrentUser = Depends(require_approved_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return _grade(MAIN, db, user.id, subject, run_id, payload)


@router.post("/lectures/{subject}/{run_id}/mainquiz/undo")
def undo_main_answer(
    subject: str,
    run_id: str,
    user: CurrentUser = Depends(require_approved_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return _undo(MAIN, db, user.id, subject, run_id)


@router.delete("/lectures/{subject}/{run_id}/mainquiz/attempts", status_code=204)
def reset_main_attempts(
    subject: str,
    run_id: str,
    user: CurrentUser = Depends(require_approved_user),
    db: Session = Depends(get_db),
) -> None:
    _reset(MAIN, db, user.id, subject, run_id)
