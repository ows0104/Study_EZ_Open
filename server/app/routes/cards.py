"""이상한 카드를 사이트에서 보고 고치거나 뺀다.

**2026-09-23 관리자 지시** — 「카드 검토를 하다가 이상한 카드가 있으면 업로드
단계에서 막히고 있어. 그러지 말고 일단 업로드를 하고, 사이트에서 이상한 카드를
검토/수정/삭제할 수 있도록 하자.」

그 전까지는 재현 검사가 「문항 결함」으로 가른 카드가 한 장이라도 남으면
문지기(`runner/gate.py`)가 **그 편의 덱 전체를** 미뤘다. 이제 문지기는 적기만
하고, 걸린 카드는 여기 목록에 뜬다.

    GET    /card-review                                   걸린 카드 전부 (편을 가로질러)
    GET    /lectures/{s}/{r}/cards/{kind}                 한 편의 카드 전부 (답까지)
    PUT    /lectures/{s}/{r}/cards/{kind}/{item_id}       괜찮다 · 고친다 · 뺀다
    DELETE /lectures/{s}/{r}/cards/{kind}/{item_id}       판정을 거두고 원본으로

## 걸린 카드는 어디서 오나

`run_meta.payload` 다 — 러너가 `run.meta.json` 을 그대로 올린다. 그 안의

    reproduce_defects        문항 결함으로 갈린 id  (전에 문지기가 막던 것)
    reproduce_defect_notes   그 사유와 재현 답      (2026-09-23 부터. 옛 편에는 없다)
    axis_unresolved          빈칸이 무엇을 묻는지 안 선 id  (막은 적은 없다)

**사유가 없는 편이 있다.** 그날 전에 만든 run.meta 에는 id 만 있다. `runner
rebuild` 를 지나면 채워진다 — 모델을 안 부르니 공짜다.

## 판정은 두 곳에 쓴다

문항 표(`pre_item`·`main_item`)에 바로 쓰고 `card_edit` 에도 적는다. 러너가
문항을 통째로 갈아 끼우기 때문이다(`admin._put_items`) — 거기서 이 표를 다시
얹는다. 이유와 「파이프라인이 바꿔 올리면 판정을 버린다」는 `models.CardEdit`.

## `.apkg` 는 안 바뀐다

여기서 고치는 것은 **웹 풀이**다. 내려받는 덱(`.apkg`)과 모아받기(`bundle/`)는
R2 의 파일을 그대로 준다. 덱까지 고치려면 `items.checked.json` 을 고쳐서
다시 굽는다(`quizgen/CLAUDE.md`).
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import CurrentUser, require_admin
from app.database import get_db
from app.models import (
    CARD_ACTIONS,
    CARD_DELETE,
    CARD_EDIT,
    CardEdit,
    Lecture,
    RunMeta,
)
from app.routes.common import lecture_or_404
from app.routes.prequiz import MAIN, PRE, Quiz, _as_utc, slide_url

router = APIRouter()

QUIZZES: dict[str, Quiz] = {"pre": PRE, "main": MAIN}

# 사람이 고칠 수 있는 칸. 나머지(`qtype`·`slide_no`…)는 파이프라인의 것이다.
EDITABLE = ("stem", "answer", "explanation")

# 원본을 들고 있을 칸. **「바꿔 올렸나」를 이것으로 잰다.**
_CARD_FIELDS = (
    "qtype", "stem", "answer", "focus", "card_type", "exam_hit", "slide_no",
    "source_type", "source_anchor", "explanation", "flags",
)
# 이 칸이 같으면 같은 카드다. `flags` 는 뺀다 — `reflag` 가 표시만 바꿔 다시
# 올리는 일이 흔하고, 그때 사람의 판정까지 날아가면 안 된다.
_SAME_CARD = ("qtype", "stem", "answer", "explanation")

# 걸린 까닭. **막던 것과 안 막던 것을 가른다** — 화면이 둘을 다르게 그린다.
WHY_DEFECT = "defect"
WHY_AXIS = "axis"


# ---------------------------------------------------------------- 표 ↔ 판정


def snapshot(row: Any) -> dict[str, Any]:
    """문항 한 줄을 원본으로 적어 둘 꼴로."""
    return {"ord": row.ord, **{name: getattr(row, name) for name in _CARD_FIELDS}}


def same_card(original: dict[str, Any], incoming: dict[str, Any]) -> bool:
    return all(original.get(name) == incoming.get(name) for name in _SAME_CARD)


def apply(row: Any, edit: CardEdit) -> None:
    """고친 칸을 문항 줄에 얹는다. `delete` 는 부르는 쪽이 줄을 안 만든다."""
    if edit.action != CARD_EDIT:
        return
    for name in EDITABLE:
        value = getattr(edit, name)
        if value is not None:
            setattr(row, name, value)


def edits_for(db: Session, subject: str, run_id: str, kind: str) -> dict[str, CardEdit]:
    return {
        edit.item_id: edit
        for edit in db.scalars(
            select(CardEdit).where(
                CardEdit.subject == subject,
                CardEdit.run_id == run_id,
                CardEdit.quiz_kind == kind,
            )
        )
    }


# ---------------------------------------------------------------- 걸린 까닭


def flagged(payload: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    """run.meta 한 벌에서 걸린 카드와 그 까닭. id → {why, reason, note, reproduced}."""
    if not isinstance(payload, dict):
        return {}
    notes = payload.get("reproduce_defect_notes") or {}
    out: dict[str, dict[str, Any]] = {}
    for item_id in payload.get("axis_unresolved") or []:
        out[str(item_id)] = {"why": WHY_AXIS, "reason": "blank_axis_missing",
                             "note": "", "reproduced": ""}
    # 결함이 축보다 무겁다 — 둘 다면 결함으로 적는다.
    for item_id in payload.get("reproduce_defects") or []:
        note = notes.get(item_id) if isinstance(notes, dict) else None
        note = note if isinstance(note, dict) else {}
        out[str(item_id)] = {
            "why": WHY_DEFECT,
            "reason": str(note.get("reason") or ""),
            "note": str(note.get("note") or ""),
            "reproduced": str(note.get("reproduced") or ""),
        }
    return out


# ---------------------------------------------------------------- 응답 꼴


def _card_payload(
    db: Session, quiz: Quiz, lecture: Lecture, item_id: str,
    row: Any | None, edit: CardEdit | None, flag: dict[str, Any] | None,
) -> dict[str, Any]:
    """카드 한 장. **뺀 카드도 원본으로 그린다** — 되돌릴 수 있어야 하니까."""
    shown = snapshot(row) if row is not None else (edit.original if edit else {})
    original = edit.original if edit else shown
    return {
        "subject": lecture.subject,
        "runId": lecture.run_id,
        "title": lecture.title,
        "date": lecture.date.isoformat(),
        "kind": quiz.name,
        "itemId": item_id,
        "ord": shown.get("ord", 0),
        "qtype": shown.get("qtype", ""),
        "stem": shown.get("stem", ""),
        "answer": shown.get("answer", ""),
        "explanation": shown.get("explanation", ""),
        "slideNo": shown.get("slide_no"),
        "slideUrl": slide_url(db, lecture.subject, lecture.run_id, shown.get("slide_no"), quiz),
        "flags": shown.get("flags") or [],
        "original": {name: original.get(name, "") for name in EDITABLE},
        "flag": flag,
        "edit": (
            {
                "action": edit.action,
                "editedBy": edit.edited_by,
                # SQLite 는 시간대를 떨어뜨린다. 붙여 보내지 않으면 화면이 제 시각으로 읽는다.
                "editedAt": _as_utc(edit.edited_at).isoformat() if edit.edited_at else None,
            }
            if edit
            else None
        ),
    }


# ---------------------------------------------------------------- 경로


@router.get("/card-review")
def card_review(
    user: CurrentUser = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """걸린 카드 전부. **올라온 카드만** 싣는다.

    run.meta 는 올라왔는데 문항 파일은 아직인 편(또는 2026-08-31 전에 구운 복습
    덱 — 웹 문항이 없다)이 있다. 그 id 를 목록에 올리면 고칠 것이 없는 줄이 선다.
    """
    lectures = {(lec.subject, lec.run_id): lec for lec in db.scalars(select(Lecture))}
    cards: list[dict[str, Any]] = []
    for meta in db.scalars(select(RunMeta)):
        quiz = QUIZZES.get(meta.quiz_kind)
        lecture = lectures.get((meta.subject, meta.run_id))
        marks = flagged(meta.payload)
        if quiz is None or lecture is None or not marks:
            continue
        edits = edits_for(db, meta.subject, meta.run_id, quiz.name)
        rows = {
            row.item_id: row
            for row in db.scalars(
                select(quiz.item).where(
                    quiz.item.subject == meta.subject,
                    quiz.item.run_id == meta.run_id,
                    quiz.item.item_id.in_(list(marks)),
                )
            )
        }
        for item_id, flag in marks.items():
            row, edit = rows.get(item_id), edits.get(item_id)
            if row is None and edit is None:
                continue
            cards.append(_card_payload(db, quiz, lecture, item_id, row, edit, flag))
    # 아직 안 본 것이 위, 그 안에서는 최근 강의부터. 정렬이 안정적이라 뒤에 건 것이 앞선다.
    cards.sort(key=lambda c: (c["runId"], c["kind"], c["ord"]))
    cards.sort(key=lambda c: c["date"], reverse=True)
    cards.sort(key=lambda c: c["edit"] is not None)
    return {
        "cards": cards,
        "open": sum(1 for c in cards if c["edit"] is None),
        "done": sum(1 for c in cards if c["edit"] is not None),
    }


def _quiz_or_404(kind: str) -> Quiz:
    quiz = QUIZZES.get(kind)
    if quiz is None:
        raise HTTPException(status_code=404, detail="갈래는 pre 나 main 입니다.")
    return quiz


@router.get("/lectures/{subject}/{run_id}/cards/{kind}")
def lecture_cards(
    subject: str,
    run_id: str,
    kind: Literal["pre", "main"],
    user: CurrentUser = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """한 편의 카드 전부, 답까지. 걸리지 않은 카드를 보다가 고칠 때 쓴다."""
    quiz = _quiz_or_404(kind)
    lecture = lecture_or_404(db, subject, run_id)
    meta = db.get(RunMeta, (lecture.subject, lecture.run_id, kind))
    marks = flagged(meta.payload if meta else None)
    edits = edits_for(db, lecture.subject, lecture.run_id, kind)
    rows = {
        row.item_id: row
        for row in db.scalars(
            select(quiz.item).where(
                quiz.item.subject == lecture.subject, quiz.item.run_id == lecture.run_id
            )
        )
    }
    ids = set(rows) | {item_id for item_id, e in edits.items() if e.action == CARD_DELETE}
    cards = [
        _card_payload(db, quiz, lecture, item_id, rows.get(item_id), edits.get(item_id),
                      marks.get(item_id))
        for item_id in ids
    ]
    cards.sort(key=lambda c: (c["ord"], c["itemId"]))
    return {"subject": lecture.subject, "runId": lecture.run_id, "title": lecture.title,
            "kind": kind, "cards": cards}


class CardDecision(BaseModel):
    """`ok` 는 원본 그대로 괜찮다, `edit` 는 준 칸만 고친다, `delete` 는 뺀다."""

    action: Literal["ok", "edit", "delete"]
    stem: str | None = None
    answer: str | None = None
    explanation: str | None = None


def _row_and_original(db: Session, quiz: Quiz, lecture: Lecture, item_id: str,
                      edit: CardEdit | None) -> tuple[Any | None, dict[str, Any]]:
    row = db.get(quiz.item, (lecture.subject, lecture.run_id, item_id))
    if edit is not None:
        return row, edit.original
    if row is None:
        raise HTTPException(status_code=404, detail="문항을 찾을 수 없습니다.")
    return row, snapshot(row)


def _restore(db: Session, quiz: Quiz, lecture: Lecture, item_id: str,
             row: Any | None, original: dict[str, Any]) -> Any:
    """원본으로 되돌린 줄. 뺐던 카드면 도로 세운다."""
    if row is None:
        row = quiz.item(subject=lecture.subject, run_id=lecture.run_id, item_id=item_id)
        db.add(row)
    row.ord = int(original.get("ord") or 0)
    for name in _CARD_FIELDS:
        if name in original:
            setattr(row, name, original[name])
    return row


@router.put("/lectures/{subject}/{run_id}/cards/{kind}/{item_id}")
def decide_card(
    subject: str,
    run_id: str,
    kind: Literal["pre", "main"],
    item_id: str,
    decision: CardDecision,
    user: CurrentUser = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """판정을 적고 문항 표에 바로 반영한다. **언제나 원본에서 다시 얹는다** —
    고친 것을 또 고치거나, 고쳤다가 「괜찮다」로 돌아서도 꼴이 하나로 선다."""
    if decision.action not in CARD_ACTIONS:  # Literal 이 이미 막지만 모델과 맞대 둔다
        raise HTTPException(status_code=422, detail="판정은 ok · edit · delete 중 하나입니다.")
    quiz = _quiz_or_404(kind)
    lecture = lecture_or_404(db, subject, run_id)
    key = (lecture.subject, lecture.run_id, kind, item_id)
    edit = db.get(CardEdit, key)
    row, original = _row_and_original(db, quiz, lecture, item_id, edit)

    if decision.action == CARD_EDIT:
        changes = {name: getattr(decision, name) for name in EDITABLE}
        changes = {k: v for k, v in changes.items() if v is not None and v != original.get(k)}
        if "answer" in changes and not changes["answer"].strip():
            raise HTTPException(status_code=422, detail="답을 비울 수는 없습니다.")
        if "stem" in changes and not changes["stem"].strip():
            raise HTTPException(status_code=422, detail="질문을 비울 수는 없습니다.")
        if not changes:
            raise HTTPException(status_code=422, detail="고친 칸이 없습니다.")
    else:
        changes = {}

    if edit is None:
        edit = CardEdit(subject=lecture.subject, run_id=lecture.run_id, quiz_kind=kind,
                        item_id=item_id, original=original)
        db.add(edit)
    edit.action = decision.action
    for name in EDITABLE:
        setattr(edit, name, changes.get(name))
    edit.edited_by = user.email or user.id

    row = _restore(db, quiz, lecture, item_id, row, original)
    if decision.action == CARD_DELETE:
        if row in db.new:  # 이미 빠져 있던 카드를 또 뺀다 — 세웠던 것을 거둔다
            db.expunge(row)
        else:
            db.delete(row)
        row = None
    else:
        apply(row, edit)
    db.commit()
    meta = db.get(RunMeta, (lecture.subject, lecture.run_id, kind))
    return _card_payload(db, quiz, lecture, item_id, row, edit,
                         flagged(meta.payload if meta else None).get(item_id))


@router.delete("/lectures/{subject}/{run_id}/cards/{kind}/{item_id}")
def undo_card_decision(
    subject: str,
    run_id: str,
    kind: Literal["pre", "main"],
    item_id: str,
    user: CurrentUser = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """판정을 거둔다. 카드는 파이프라인이 올린 원본으로, 목록에서는 「안 봄」으로."""
    quiz = _quiz_or_404(kind)
    lecture = lecture_or_404(db, subject, run_id)
    edit = db.get(CardEdit, (lecture.subject, lecture.run_id, kind, item_id))
    if edit is None:
        raise HTTPException(status_code=404, detail="거둘 판정이 없습니다.")
    row = db.get(quiz.item, (lecture.subject, lecture.run_id, item_id))
    row = _restore(db, quiz, lecture, item_id, row, edit.original)
    db.delete(edit)
    db.commit()
    meta = db.get(RunMeta, (lecture.subject, lecture.run_id, kind))
    return _card_payload(db, quiz, lecture, item_id, row, None,
                         flagged(meta.payload if meta else None).get(item_id))
