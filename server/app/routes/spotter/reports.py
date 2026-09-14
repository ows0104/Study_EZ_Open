"""문항 제보와 제보함. 사람이 「이 문항 이상하다」고 누르는 자리."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import CurrentUser, require_admin
from app.database import get_db
from app.models import (
    SPOTTER_ALERT_MIN,
    SPOTTER_REPORT_KINDS,
    SPOTTER_REPORT_OPEN,
    SPOTTER_REPORT_STATUSES,
    Profile,
    SpotterReport,
)
from app.routes.spotter.common import (
    _hot_images,
    _hot_questions,
    _image_names,
    _iso,
    require_spotter,
)

# 제보가 들어오면 그 자리의 글타래가 서야 한다. **화살표는 한 방향이다** —
# 게시판은 제보를 모르고(공용 헬퍼만 쓴다), 제보가 게시판을 부른다.
from app.routes.spotter.threads import ensure_threads

router = APIRouter()


# ── 문항 제보 ────────────────────────────────────────────────────────


class ReportIn(BaseModel):
    question_id: str = Field(alias="questionId")
    kind: str = "other"
    note: str = ""
    stem: str = ""
    answer: str = ""
    image: str = ""
    # 사진 파일명만. `image`(사람이 읽는 줄)와 갈라 두는 까닭은 모델에 적혀 있다.
    images: list[str] = Field(default_factory=list)

    model_config = {"populate_by_name": True}




def _report_row(row: SpotterReport, email: str = "") -> dict[str, Any]:
    return {
        "id": row.id,
        "questionId": row.question_id,
        "kind": row.kind,
        "note": row.note,
        "stem": row.stem,
        "answer": row.answer,
        "image": row.image,
        "images": _image_names(row),
        "status": row.status,
        "adminNote": row.admin_note,
        "at": _iso(row.created_at),
        "email": email,
    }


@router.post("/reports")
def create_report(
    payload: ReportIn,
    user: CurrentUser = Depends(require_spotter),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """「이 문항 이상해요」.

    문항이 자동 생성이라(오답 보기도 마스터 표에서 뽑는다) 사람이 걸러 주는
    자리가 없으면 틀린 문항이 조용히 남는다. 화면 아래 작은 글씨로 "오류가
    있을 수 있습니다"라고 적어 두는 것과 그 자리에서 제보를 받는 것은 다르다.

    같은 사람이 같은 문항을 다시 제보하면 **줄을 고쳐 쓴다.** 목록에서 세는
    것은 몇 명이 걸렸는가지 몇 번 눌렀는가가 아니다.
    """
    qid = payload.question_id.strip()
    if not qid:
        raise HTTPException(status_code=400, detail="문항을 알 수 없습니다.")

    row = db.scalar(
        select(SpotterReport).where(
            SpotterReport.user_id == user.id, SpotterReport.question_id == qid
        )
    )
    if row is None:
        row = SpotterReport(user_id=user.id, question_id=qid)
        db.add(row)
    row.kind = payload.kind if payload.kind in SPOTTER_REPORT_KINDS else "other"
    row.note = payload.note.strip()[:2000]
    # 제보 당시의 문면. 지금의 문항이 아니다 — 모델의 설명을 보라.
    row.stem = payload.stem.strip()[:1000]
    row.answer = payload.answer.strip()[:500]
    row.image = payload.image.strip()[:300]
    row.images = ", ".join(name.strip() for name in payload.images if name.strip())[:600]
    # 다시 제보했다는 것은 아직 안 고쳐졌다는 뜻이다. 닫혀 있었으면 연다.
    row.status = SPOTTER_REPORT_OPEN
    db.commit()
    ensure_threads(db)
    return _report_row(row, user.email)


@router.get("/reports/mine")
def list_my_reports(
    user: CurrentUser = Depends(require_spotter), db: Session = Depends(get_db)
) -> dict[str, Any]:
    """내가 낸 제보. 화면이 「제보함」 표시를 다는 데 쓴다."""
    rows = db.scalars(
        select(SpotterReport)
        .where(SpotterReport.user_id == user.id)
        .order_by(SpotterReport.created_at.desc())
    ).all()
    return {"reports": [_report_row(row, user.email) for row in rows]}


# ── 제보함(관리자) ───────────────────────────────────────────────────


@router.get("/admin/reports")
def list_reports(
    status: str = "", user: CurrentUser = Depends(require_admin), db: Session = Depends(get_db)
) -> dict[str, Any]:
    """들어온 제보 전부. **문항으로 묶어서** 낸다.

    먼저 볼 것은 여럿이 걸린 문항이다. 한 사람이 잘못 읽은 것과 열 명이 같은
    자리에서 멈춘 것은 다른 일이고, 시간이 한정되면 뒤쪽을 먼저 고쳐야 한다.
    시각순으로 늘어놓으면 그 구분이 목록에서 사라진다.
    """
    query = select(SpotterReport).order_by(SpotterReport.created_at.desc())
    if status in SPOTTER_REPORT_STATUSES:
        query = query.where(SpotterReport.status == status)
    rows = db.scalars(query).all()

    user_ids = {row.user_id for row in rows}
    emails = {
        profile.id: profile.email
        for profile in db.scalars(select(Profile).where(Profile.id.in_(user_ids or {""}))).all()
    }

    groups: dict[str, dict[str, Any]] = {}
    for row in rows:
        group = groups.setdefault(
            row.question_id, {"questionId": row.question_id, "open": 0, "reports": []}
        )
        group["reports"].append(_report_row(row, emails.get(row.user_id, "")))
        if row.status == SPOTTER_REPORT_OPEN:
            group["open"] += 1

    # 여럿이 걸린 문항. 세는 것은 `_hot_questions`이고 화면은 받아 그리기만
    # 한다 — 선을 옮길 때 두 군데를 고치게 두면 화면과 서버가 갈린다.
    hot = _hot_questions(rows)
    for question_id, group in groups.items():
        group["hot"] = question_id in hot

    ordered = sorted(
        groups.values(), key=lambda g: (-g["open"], -len(g["reports"]), g["reports"][0]["at"])
    )
    hot_questions = [g for g in ordered if g["hot"]]
    hot_images = _hot_images(rows)
    return {
        "groups": ordered,
        "total": len(rows),
        "images": hot_images,
        # 화면 맨 위의 배지가 읽는 값. `min`까지 함께 내는 것은 「3명 이상」이라고
        # 적을 사람이 화면이기 때문이다 — 선을 서버에서 옮기면 글자도 따라온다.
        "alert": {
            "min": SPOTTER_ALERT_MIN,
            "questions": len(hot_questions),
            "images": len(hot_images),
        },
    }






class ReportPatch(BaseModel):
    status: str = ""
    admin_note: str = Field(default="", alias="adminNote")

    model_config = {"populate_by_name": True}


@router.patch("/admin/reports/{report_id}")
def update_report(
    report_id: int,
    payload: ReportPatch,
    user: CurrentUser = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    row = db.get(SpotterReport, report_id)
    if row is None:
        raise HTTPException(status_code=404, detail="없는 제보입니다.")
    if payload.status:
        if payload.status not in SPOTTER_REPORT_STATUSES:
            raise HTTPException(status_code=400, detail="상태 값이 올바르지 않습니다.")
        row.status = payload.status
    row.admin_note = payload.admin_note.strip()[:2000]
    db.commit()
    return _report_row(row)
