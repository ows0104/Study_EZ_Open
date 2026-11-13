"""자유 노트: 계정별 블록 노트. 본인 노트만 읽고 쓴다(남의 id는 404)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import CurrentUser, require_approved_user
from app.database import get_db
from app.models.base import _now
from app.models.notes import UserNote

router = APIRouter()

MAX_NOTES = 500
MAX_TAGS = 30
MAX_TAG_LEN = 40

BlockType = Literal["text", "h1", "h2", "h3", "bullet", "number", "todo", "quote", "callout", "code", "divider", "image"]
# 사진 블록은 이 브라우저(IndexedDB)에 둔 사진의 id만 서버에 둔다. 사진 바이트는 서버로 오지 않는다(2026-11-13 사용자 지시).
IMAGE_ID = r"^[a-z0-9]{8,40}$"


class BlockIn(BaseModel):
    id: str = Field(min_length=1, max_length=40)
    type: BlockType
    html: str = Field(default="", max_length=20_000)
    checked: bool = False
    image: str | None = Field(default=None, pattern=IMAGE_ID)

    @model_validator(mode="after")
    def image_needs_id(self) -> "BlockIn":
        if self.type == "image" and not self.image:
            raise ValueError("사진 블록에는 사진 id가 필요합니다.")
        return self


class NoteIn(BaseModel):
    title: str = Field(default="", max_length=200)
    tags: list[str] = Field(default_factory=list, max_length=200)
    blocks: list[BlockIn] = Field(default_factory=list, max_length=2000)

    @field_validator("tags")
    @classmethod
    def clean_tags(cls, tags: list[str]) -> list[str]:
        out: list[str] = []
        for tag in tags:
            tag = " ".join(tag.split())
            if not tag:
                continue
            if len(tag) > MAX_TAG_LEN:
                raise ValueError(f"태그는 {MAX_TAG_LEN}자까지입니다.")
            if tag not in out:
                out.append(tag)
        if len(out) > MAX_TAGS:
            raise ValueError(f"태그는 {MAX_TAGS}개까지입니다.")
        return out


def _iso(value: datetime | None) -> str:
    # sqlite는 시간대를 버린다. 저장값은 언제나 UTC라 없으면 UTC로 붙여 웹이 현지 시각으로 오인하지 않게 한다.
    if value is None:
        return ""
    return (value if value.tzinfo else value.replace(tzinfo=UTC)).isoformat()


def _summary(note: UserNote) -> dict:
    return {"id": note.id, "title": note.title, "tags": list(note.tags or []), "updatedAt": _iso(note.updated_at)}


def _full(note: UserNote) -> dict:
    return {**_summary(note), "blocks": list(note.blocks or [])}


def _blocks(payload: NoteIn) -> list[dict]:
    out = []
    for b in payload.blocks:
        block = {"id": b.id, "type": b.type, "html": "" if b.type in ("divider", "image") else b.html}
        if b.type == "image":
            block["image"] = b.image
        if b.type == "todo":
            block["checked"] = b.checked
        out.append(block)
    return out


def _own(db: Session, user: CurrentUser, note_id: str) -> UserNote:
    note = db.get(UserNote, note_id)
    if note is None or note.user_id != user.id:
        raise HTTPException(404, "노트를 찾을 수 없습니다.")
    return note


@router.get("/me/notes")
def list_notes(user: CurrentUser = Depends(require_approved_user), db: Session = Depends(get_db)) -> dict:
    notes = db.scalars(select(UserNote).where(UserNote.user_id == user.id)
                       .order_by(UserNote.updated_at.desc(), UserNote.id)).all()
    return {"notes": [_summary(n) for n in notes]}


@router.post("/me/notes")
def create_note(payload: NoteIn, user: CurrentUser = Depends(require_approved_user),
                db: Session = Depends(get_db)) -> dict:
    count = db.scalar(select(func.count()).select_from(UserNote).where(UserNote.user_id == user.id)) or 0
    if count >= MAX_NOTES:
        raise HTTPException(409, f"노트는 {MAX_NOTES}개까지 만들 수 있습니다.")
    now = _now()
    note = UserNote(id=uuid.uuid4().hex, user_id=user.id, title=payload.title, tags=payload.tags,
                    blocks=_blocks(payload), created_at=now, updated_at=now)
    db.add(note)
    db.commit()
    return _full(note)


@router.get("/me/notes/{note_id}")
def read_note(note_id: str, user: CurrentUser = Depends(require_approved_user),
              db: Session = Depends(get_db)) -> dict:
    return _full(_own(db, user, note_id))


@router.put("/me/notes/{note_id}")
def write_note(note_id: str, payload: NoteIn, user: CurrentUser = Depends(require_approved_user),
               db: Session = Depends(get_db)) -> dict:
    note = _own(db, user, note_id)
    note.title = payload.title
    note.tags = payload.tags
    note.blocks = _blocks(payload)
    note.updated_at = _now()
    db.commit()
    return _full(note)


@router.delete("/me/notes/{note_id}")
def delete_note(note_id: str, user: CurrentUser = Depends(require_approved_user),
                db: Session = Depends(get_db)) -> dict:
    db.delete(_own(db, user, note_id))
    db.commit()
    return {"ok": True}
