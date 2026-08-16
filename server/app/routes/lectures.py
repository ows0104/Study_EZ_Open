"""강의 상세. 작년 강의록 · 예습 열기 · Pre-Quiz · 올해 강의록 · Main-Quiz.

파일은 목록에만 나오고, 실제 URL은 누를 때 따로 받는다. 서명 URL의 수명이
분 단위라 미리 실어 보내면 화면을 열어 둔 사이에 죽는다.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import CurrentUser, get_current_user
from app.config import get_settings
from app.database import get_db
from app.models import Asset, PreItem, Preview, QuizAttempt, RunMeta, TimetableEvent
from app.routes.common import lecture_or_404
from app.routes.prequiz import missed_items
from app.storage import ObjectStorage

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
    """예습 링크.

    `share_url`이 기본이다. 퀴즈를 만들 때 쓰는 링크가 이것이고 모두에게 보인다.

    `conversation_url`(`/c/`)은 **결국 모두에게 줄 것이다.** 지금 관리자에게만
    나가는 것은 그 링크가 아직 불안정하기 때문이지 감춰야 할 값이라서가 아니다.
    안정되면 `STUDYEZ_SHOW_CONVERSATION_URL`을 켜면 되고 코드는 그대로다.
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
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    lecture = lecture_or_404(db, subject, run_id)

    assets = db.scalars(
        select(Asset)
        .where(Asset.subject == lecture.subject, Asset.run_id == lecture.run_id, Asset.kind.in_(DOWNLOADABLE))
        .order_by(Asset.kind, Asset.filename)
    ).all()
    preview = db.get(Preview, (lecture.subject, lecture.run_id))
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
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """누를 때 발급하는 짧은 수명의 서명 URL. 제3자 저작물이라 다른 경로는 없다."""
    lecture = lecture_or_404(db, subject, run_id)
    asset = db.get(Asset, asset_id)
    if asset is None or (asset.subject, asset.run_id) != (lecture.subject, lecture.run_id):
        raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")
    return {
        "url": ObjectStorage().presign_download(asset.object_key, filename=asset.filename),
        "expiresIn": get_settings().signed_url_ttl,
        "filename": asset.filename,
    }
