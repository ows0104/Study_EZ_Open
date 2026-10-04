"""공지사항. 읽기는 승인된 사람, 쓰기는 관리자.

2026-10-04 운영을 시작하며 섰다(`models.Notice` 머리). 쓰는 경로가 `/api/admin`
아래인 것은 다른 관리 경로와 같은 자리에 두려는 것뿐이고, 문은 `require_admin` 이다.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import CurrentUser, require_admin, require_approved_user
from app.database import get_db
from app.models import Notice

router = APIRouter()
admin_router = APIRouter()


class NoticeIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(default="", max_length=20000)
    pinned: bool = False


def notice_row(row: Notice) -> dict[str, Any]:
    return {
        "id": row.id,
        "title": row.title,
        "body": row.body,
        "pinned": row.pinned,
        "createdAt": row.created_at.isoformat() if row.created_at else None,
        "updatedAt": row.updated_at.isoformat() if row.updated_at else None,
    }


@router.get("/notices")
def list_notices(
    _: CurrentUser = Depends(require_approved_user),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """고정이 먼저, 그 안에서 새 글이 먼저."""
    rows = db.scalars(
        select(Notice).order_by(Notice.pinned.desc(), Notice.created_at.desc(), Notice.id.desc())
    ).all()
    return [notice_row(row) for row in rows]


def _clean(payload: NoticeIn) -> tuple[str, str]:
    title = payload.title.strip()
    if not title:
        raise HTTPException(status_code=422, detail="제목이 비어 있습니다.")
    return title, payload.body.strip()


@admin_router.post("/notices")
def create_notice(
    payload: NoticeIn,
    user: CurrentUser = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    title, body = _clean(payload)
    row = Notice(title=title, body=body, pinned=payload.pinned, created_by=user.email)
    db.add(row)
    db.commit()
    db.refresh(row)
    return notice_row(row)


@admin_router.put("/notices/{notice_id}")
def update_notice(
    notice_id: int,
    payload: NoticeIn,
    _: CurrentUser = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    row = db.get(Notice, notice_id)
    if row is None:
        raise HTTPException(status_code=404, detail="없는 공지입니다.")
    row.title, row.body = _clean(payload)
    row.pinned = payload.pinned
    db.commit()
    db.refresh(row)
    return notice_row(row)


@admin_router.delete("/notices/{notice_id}", status_code=204)
def delete_notice(
    notice_id: int,
    _: CurrentUser = Depends(require_admin),
    db: Session = Depends(get_db),
) -> None:
    row = db.get(Notice, notice_id)
    if row is None:
        raise HTTPException(status_code=404, detail="없는 공지입니다.")
    db.delete(row)
    db.commit()
