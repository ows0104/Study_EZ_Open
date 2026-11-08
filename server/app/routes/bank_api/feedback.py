"""Student question reports and admin triage."""

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import CurrentUser, require_admin, require_approved_user
from app.bank_validation.priorities import priority_fields
from app.database import get_db
from app.models import BankFeedback, Lecture, Profile, QuizBank
from app.routes.common import lecture_or_404

from .common import _bank_or_404, _iso
from .state import _study_bank


router = APIRouter()


admin_router = APIRouter()


FEEDBACK_CATEGORIES = ("good", "wording", "easy", "hard", "leak", "format", "burden", "importance",
                       "content", "duplicate", "sequencing", "other")
FEEDBACK_STATUSES = ("open", "resolved", "wontfix")


@admin_router.get("/bank-feedback")
def bank_feedback(user: CurrentUser = Depends(require_admin), db: Session = Depends(get_db)) -> dict[str, Any]:
    """학생의 「문제 있음」을 편을 가로질러 **문항별로** 묶는다 — 관리 화면 「Quiz Bank 신고」 탭.

    여럿이 같은 문항을 신고하면 한 묶음이다. 문항은 **지금 은행의 것**을 싣는다 — 신고 줄에는
    문면이 없다. 그래서 신고가 옛 빌드에서 왔으면 `stale` 로 갈라 둔다: 다시 만들면 ChatGPT 가
    같은 ID(Q7)에 다른 문항을 낼 수 있어서, 지금 문항을 두고 옛 신고를 읽으면 엉뚱한 판정이 된다.

    `good`(좋은 문제)은 신고가 아니라서 뺀다. 화면의 폼에는 없고 서버만 받는 값이다.
    """
    rows = db.scalars(select(BankFeedback).where(BankFeedback.category != "good")
                      .order_by(BankFeedback.created_at.desc())).all()
    banks: dict[tuple[str, str], QuizBank | None] = {}
    lectures: dict[tuple[str, str], Lecture | None] = {}
    emails = {p.id: p.email for p in db.scalars(select(Profile).where(
        Profile.id.in_({f.user_id for f in rows})))} if rows else {}
    groups: dict[tuple[str, str, str], dict[str, Any]] = {}
    roots: dict[tuple[str, str], tuple[str | None, dict[str, dict]]] = {}

    def root_question(f: BankFeedback) -> tuple[dict | None, bool]:
        """Main-Quiz 제보(build_id `root:<판>`)는 그 판의 문항 문면을 싣는다. 지금 공개 판이 아니면 stale."""
        key = (f.subject, f.run_id)
        if key not in roots:
            from app.models.root_learning import RootContent, RootControl
            control = db.get(RootControl, key)
            revisions = {("root:" + r)[:64]: r for r in db.scalars(select(RootContent.revision).where(
                RootContent.subject == f.subject, RootContent.run_id == f.run_id))}
            roots[key] = (control.revision if control else None, revisions)
        active, revisions = roots[key]
        revision = revisions.get(f.build_id)
        if revision is None:
            return None, True
        from app.models.root_learning import RootContent
        doc = db.get(RootContent, (f.subject, f.run_id, revision))
        q = next((q for q in doc.document["bank_snapshot"]["questions"] if q["question_id"] == f.question_id), None)
        # Main-Quiz 문항은 빈 목록 칸을 생략한다. 신고함 카드는 기존 은행 문항처럼 모든 칸이 있다고 읽는다.
        empty = {k: [] for k in ("options", "answer_pairs", "correct_option_ids", "correct_order", "answer_units")}
        return ({**empty, "answer": "", **q} if q else None), revision != active

    for f in rows:
        key = (f.subject, f.run_id)
        if key not in banks:
            banks[key] = db.get(QuizBank, key)
            lectures[key] = db.get(Lecture, key)
        bank, lecture = banks[key], lectures[key]
        main_quiz = f.build_id.startswith("root:")
        root_q, root_stale = root_question(f) if main_quiz else (None, False)
        group = groups.get((*key, f.question_id))
        if group is None:
            questions = (bank.bank or {}).get("questions", []) if bank else []
            q = root_q if main_quiz else next((q for q in questions if q["question_id"] == f.question_id), None)
            review = next((r for r in ((bank.review or {}).get("reviews", []) if bank else [])
                           if r["question_id"] == f.question_id), None)
            group = groups[(*key, f.question_id)] = {
                "subject": f.subject, "runId": f.run_id, "questionId": f.question_id,
                "title": lecture.title if lecture else "", "date": lecture.date.isoformat() if lecture else "",
                "question": priority_fields(q, question=True) if q else None, "medicalReview": review, "reports": [],
            }
        group["reports"].append({
            "id": f.id, "category": f.category, "comment": f.comment, "status": f.status,
            "highlighted": f.highlighted,
            "email": emails.get(f.user_id, ""), "createdAt": _iso(f.created_at),
            "stale": root_stale if main_quiz else bank is None or f.build_id != bank.build_id,
            "mainQuiz": main_quiz,
        })
    out = list(groups.values())
    out.sort(key=lambda g: any(r["highlighted"] and r["status"] == "open" for r in g["reports"]), reverse=True)
    open_count = sum(1 for g in out if any(r["status"] == "open" for r in g["reports"]))
    return {"questions": out, "open": open_count, "done": len(out) - open_count}


class FeedbackStatusIn(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=500)
    status: Literal[FEEDBACK_STATUSES]  # type: ignore[valid-type]


@admin_router.put("/bank-feedback")
def set_bank_feedback_status(payload: FeedbackStatusIn, user: CurrentUser = Depends(require_admin),
                             db: Session = Depends(get_db)) -> dict[str, Any]:
    """신고 여럿의 상태를 한 번에 — 반영했다(resolved) · 그대로 둔다(wontfix) · 되돌린다(open)."""
    rows = db.scalars(select(BankFeedback).where(BankFeedback.id.in_(payload.ids))).all()
    if len(rows) != len(set(payload.ids)):
        raise HTTPException(404, "없는 신고가 섞여 있습니다.")
    for row in rows:
        row.status = payload.status
    db.commit()
    return {"updated": len(rows)}


class FeedbackIn(BaseModel):
    # Keep the published OpenAPI component name when another router also
    # defines FeedbackIn. Pydantic uses the module to disambiguate them.
    __module__ = "app.routes.bank"
    question_id: str = Field(alias="questionId", max_length=64)
    category: Literal[FEEDBACK_CATEGORIES]  # type: ignore[valid-type]
    comment: str = Field(default="", max_length=2000)

    model_config = {"populate_by_name": True}


@router.post("/lectures/{subject}/{run_id}/bank/feedback", status_code=201)
def post_bank_feedback(subject: str, run_id: str, payload: FeedbackIn,
                       user: CurrentUser = Depends(require_approved_user), db: Session = Depends(get_db)) -> dict:
    lecture = lecture_or_404(db, subject, run_id)
    row = _bank_or_404(db, lecture, user)
    bank = _study_bank(db, row, user)
    if not any(q["question_id"] == payload.question_id for q in bank["questions"]):
        raise HTTPException(404, "문항을 찾을 수 없습니다.")
    entry = BankFeedback(user_id=user.id, subject=row.subject, run_id=row.run_id, build_id=row.build_id,
                         question_id=payload.question_id, category=payload.category, comment=payload.comment)
    db.add(entry)
    db.commit()
    return {"id": entry.id}
