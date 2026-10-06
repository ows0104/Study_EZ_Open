"""학생의 의견 접수와 관리자 전용 피드백함."""

import base64
import binascii
import io
import logging
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import CurrentUser, require_admin, require_approved_user
from app.database import get_db
from app.models.feedback import SiteFeedback
from app.storage import ObjectStorage, StorageNotConfigured

router = APIRouter()
MAX_IMAGE_BYTES = 3 * 1024 * 1024


class ScreenshotIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    data: str = Field(min_length=1, max_length=4 * ((MAX_IMAGE_BYTES + 2) // 3))


class FeedbackIn(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    page: str = Field(default="", max_length=1000)
    screenshots: list[ScreenshotIn] = Field(default_factory=list, max_length=3)


class StatusIn(BaseModel):
    status: Literal["open", "resolved"]


def _image(screenshot: ScreenshotIn) -> tuple[bytes, str, str]:
    try:
        data = base64.b64decode(screenshot.data, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(422, "캡처 파일을 읽지 못했습니다.") from exc
    if not data or len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(422, "캡처는 한 장당 3MB 이하로 첨부해 주세요.")
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return data, "image/png", "png"
    if data.startswith(b"\xff\xd8\xff"):
        return data, "image/jpeg", "jpg"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return data, "image/webp", "webp"
    raise HTTPException(422, "PNG, JPG, WebP 캡처만 첨부할 수 있습니다.")


def _storage() -> ObjectStorage:
    try:
        return ObjectStorage()
    except StorageNotConfigured as exc:
        raise HTTPException(503, "캡처 저장소가 준비되지 않았습니다. 잠시 뒤 다시 보내 주세요.") from exc


@router.post("/feedback", status_code=201)
def submit_feedback(
    payload: FeedbackIn,
    user: CurrentUser = Depends(require_approved_user),
    db: Session = Depends(get_db),
) -> dict:
    message = payload.message.strip()
    if not message:
        raise HTTPException(422, "의견을 입력해 주세요.")
    images = [(screenshot, _image(screenshot)) for screenshot in payload.screenshots]
    storage = _storage() if images else None
    attachments = []
    uploaded = []
    try:
        for screenshot, (data, content_type, extension) in images:
            key = f"feedback/{uuid4().hex}.{extension}"
            uploaded.append(key)
            storage.upload_fileobj(io.BytesIO(data), key, content_type=content_type)
            attachments.append({"name": screenshot.name, "key": key, "contentType": content_type})
        row = SiteFeedback(
            user_id=user.id, email=user.email, message=message,
            page=payload.page, screenshots=attachments,
        )
        db.add(row)
        db.flush()
        feedback_id = row.id
        db.commit()
    except Exception as exc:
        db.rollback()
        for key in uploaded:
            try:
                storage.delete(key)
            except Exception:
                logging.getLogger(__name__).exception("피드백 첨부 정리 실패")
        raise HTTPException(503, "피드백을 저장하지 못했습니다. 잠시 뒤 다시 보내 주세요.") from exc
    return {"id": feedback_id}


@router.get("/admin/feedback")
def feedback_board(
    user: CurrentUser = Depends(require_admin), db: Session = Depends(get_db),
) -> list[dict]:
    rows = db.scalars(select(SiteFeedback).order_by(SiteFeedback.id.desc()).limit(200)).all()
    return [{
        "id": row.id, "email": row.email, "message": row.message, "page": row.page,
        "status": row.status, "createdAt": row.created_at.isoformat(),
        "screenshots": [{"name": shot["name"]} for shot in row.screenshots],
    } for row in rows]


@router.patch("/admin/feedback/{feedback_id}")
def update_feedback(
    feedback_id: int, payload: StatusIn,
    user: CurrentUser = Depends(require_admin), db: Session = Depends(get_db),
) -> dict:
    row = db.get(SiteFeedback, feedback_id)
    if row is None:
        raise HTTPException(404, "피드백이 없습니다.")
    row.status = payload.status
    db.commit()
    return {"id": row.id, "status": row.status}


@router.get("/admin/feedback/{feedback_id}/screenshots/{index}")
def feedback_screenshot(
    feedback_id: int, index: int,
    user: CurrentUser = Depends(require_admin), db: Session = Depends(get_db),
) -> Response:
    row = db.get(SiteFeedback, feedback_id)
    if row is None or index < 0 or index >= len(row.screenshots):
        raise HTTPException(404, "캡처가 없습니다.")
    shot = row.screenshots[index]
    data = _storage().get_bytes(shot["key"])
    if data is None:
        raise HTTPException(404, "캡처가 없습니다.")
    # 작은 첨부만 인증 후 전달한다. 로컬 저장소의 공개 경로에도 노출하지 않는다.
    return Response(data, media_type=shot["contentType"], headers={
        "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff",
    })
