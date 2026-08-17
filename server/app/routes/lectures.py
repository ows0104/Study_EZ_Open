"""강의 상세. 작년 강의록 · 예습 열기 · Pre-Quiz · 올해 강의록 · Main-Quiz.

파일은 목록에만 나오고, 실제 URL은 누를 때 따로 받는다. 서명 URL에는 수명이
있어서 미리 실어 보내면 화면을 열어 둔 사이에 죽는다.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import CurrentUser, require_approved_user
from app.config import get_settings
from app.database import get_db
from app.models import Asset, PreItem, Preview, QuizAttempt, RunMeta, TimetableEvent, UserPreview
from app.routes.common import lecture_or_404, storage_or_503
from app.routes.prequiz import missed_items

router = APIRouter()

# 파일 목록에 나가는 종류와 화면에 쓰는 이름. `media`는 여기 없다 — 슬라이드
# 이미지는 오답 해설이 알아서 띄우는 것이지 사용자가 내려받는 것이 아니다.
DOWNLOADABLE = {
    "notes_prev": "작년 강의록",
    "notes_current": "올해 강의록",
    "pre_apkg": "Pre-Quiz 덱",
    "main_apkg": "Main-Quiz 덱",
}


def _preview_payload(preview: Preview | None, *, is_admin: bool) -> dict[str, Any] | None:
    """기본 링크. 강의당 하나이고 반 전체가 같은 것을 읽는다.

    `share_url`이 그것이다 — `/share/` 주소라 링크를 가진 누구나 열 수 있고,
    Pre-Quiz를 만들 때 읽는 것도 이쪽이다.

    `conversation_url`(`/c/`)은 만든 사람 계정에서만 열린다. 개인 링크가 생긴
    뒤로 이 칸은 "기본 링크를 누가 만들었나"의 흔적으로만 남는다 — 사람이 자기
    대화를 여는 자리는 `user_preview`다.
    """
    if preview is None or not (preview.share_url or preview.conversation_url):
        return None
    payload: dict[str, Any] = {"provider": preview.provider, "shareUrl": preview.share_url}
    if preview.conversation_url and (is_admin or get_settings().show_conversation_url):
        payload["conversationUrl"] = preview.conversation_url
    return payload


@router.get("/lectures/{subject}/{run_id}")
def read_lecture(
    subject: str,
    run_id: str,
    user: CurrentUser = Depends(require_approved_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    lecture = lecture_or_404(db, subject, run_id)

    assets = db.scalars(
        select(Asset)
        .where(Asset.subject == lecture.subject, Asset.run_id == lecture.run_id, Asset.kind.in_(DOWNLOADABLE))
        .order_by(Asset.kind, Asset.filename)
    ).all()
    preview = db.get(Preview, (lecture.subject, lecture.run_id))
    my_preview = db.get(UserPreview, (user.id, lecture.subject, lecture.run_id))
    item_count = db.scalar(
        select(func.count()).select_from(PreItem).where(
            PreItem.subject == lecture.subject, PreItem.run_id == lecture.run_id
        )
    )
    mine = (
        QuizAttempt.user_id == user.id,
        QuizAttempt.subject == lecture.subject,
        QuizAttempt.run_id == lecture.run_id,
    )
    answered = int(db.scalar(select(func.count()).select_from(QuizAttempt).where(*mine)) or 0)
    correct = int(
        db.scalar(
            select(func.count()).select_from(QuizAttempt).where(*mine, QuizAttempt.correct.is_(True))
        )
        or 0
    )

    event = (
        db.get(TimetableEvent, lecture.timetable_event_id) if lecture.timetable_event_id else None
    )

    payload: dict[str, Any] = {
        "subject": lecture.subject,
        "runId": lecture.run_id,
        "uid": lecture.uid,
        "date": lecture.date.isoformat(),
        "slot": lecture.slot,
        "slotEnd": lecture.slot_end,
        "startTime": lecture.start_time,
        "title": lecture.title,
        "professors": lecture.professors,
        "author": lecture.author,
        "version": lecture.version,
        "course": event.course if event else "",
        "files": [
            {
                "id": asset.id,
                "kind": asset.kind,
                "label": DOWNLOADABLE[asset.kind],
                "filename": asset.filename,
                "sizeBytes": asset.size_bytes,
            }
            for asset in assets
        ],
        "preview": _preview_payload(preview, is_admin=user.is_admin),
        # 내 개인 대화. 남의 것은 절대 안 나간다 — `/c/`는 만든 계정에서만
        # 열리므로 남에게 주면 죽은 링크이고, 무엇을 물었는지만 새어 나간다.
        "myPreview": (
            {"conversationUrl": my_preview.conversation_url}
            if my_preview and my_preview.conversation_url
            else None
        ),
        "prequiz": (
            {
                "itemCount": int(item_count or 0),
                "answered": answered,
                "correct": correct,
                # 다 풀었을 때만 보여 준다. 두 문제 풀고 나온 "놓친 것"은
                # 청취 목표가 아니라 진행 상황일 뿐이다.
                "missed": (
                    missed_items(db, user.id, lecture.subject, lecture.run_id)
                    if item_count and answered >= int(item_count)
                    else []
                ),
            }
            if item_count
            else None
        ),
    }

    if user.is_admin:
        payload["runMeta"] = {
            meta.quiz_kind: {
                "reviewFlagged": meta.review_flagged,
                "slidesUnused": meta.slides_unused,
                "itemCount": meta.item_count,
                "builtAt": meta.built_at.isoformat() if meta.built_at else None,
                "payload": meta.payload,
            }
            for meta in db.scalars(
                select(RunMeta).where(
                    RunMeta.subject == lecture.subject, RunMeta.run_id == lecture.run_id
                )
            )
        }
    return payload


@router.get("/lectures/{subject}/{run_id}/files/{asset_id}")
def sign_file(
    subject: str,
    run_id: str,
    asset_id: str,
    user: CurrentUser = Depends(require_approved_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """누를 때 발급하는 서명 URL. 버킷이 비공개라 이 경로로만 파일이 열린다."""
    lecture = lecture_or_404(db, subject, run_id)
    asset = db.get(Asset, asset_id)
    if asset is None or (asset.subject, asset.run_id) != (lecture.subject, lecture.run_id):
        raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")
    return {
        "url": storage_or_503().presign_download(asset.object_key, filename=asset.filename),
        "expiresIn": get_settings().signed_url_ttl,
        "filename": asset.filename,
    }


class MyPreviewIn(BaseModel):
    conversation_url: str = Field(default="", alias="conversationUrl")

    model_config = {"populate_by_name": True}


@router.put("/lectures/{subject}/{run_id}/my-preview")
def put_my_preview(
    subject: str,
    run_id: str,
    payload: MyPreviewIn,
    user: CurrentUser = Depends(require_approved_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """내 개인 예습 대화를 저장한다.

    **관리자 게이트가 없다.** 기본 링크(`PUT /api/admin/…/preview`)는 반 전체가
    읽는 값이라 관리자만 쓰지만, 이것은 자기 것이다. 주인은 토큰이 정하고
    경로에는 안 들어간다 — 들어가면 남의 자리에 쓸 수 있게 된다.

    빈 문자열을 주는 것이 곧 지우기다.
    """
    lecture = lecture_or_404(db, subject, run_id)
    mine = db.get(UserPreview, (user.id, lecture.subject, lecture.run_id))
    if mine is None:
        mine = UserPreview(user_id=user.id, subject=lecture.subject, run_id=lecture.run_id)
        db.add(mine)
    mine.conversation_url = payload.conversation_url.strip()
    db.commit()
    return {"conversationUrl": mine.conversation_url}
