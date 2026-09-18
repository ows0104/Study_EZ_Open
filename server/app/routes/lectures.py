"""강의 상세. 작년 강의록 · 예습 열기 · Pre-Quiz · 올해 강의록 · Main-Quiz.

파일은 목록에만 나오고, 실제 URL은 누를 때 따로 받는다. 서명 URL에는 수명이
있어서 미리 실어 보내면 화면을 열어 둔 사이에 죽는다.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import CurrentUser, require_approved_user
from app.config import get_settings
from app.database import get_db
from app.models import (
    Asset,
    Lecture,
    Preview,
    RunMeta,
    TimetableEvent,
    UserPreview,
)
from app.preview_links import conversation_url as valid_conversation_url
from app.preview_links import provider as valid_provider
from app.routes.common import lecture_or_404, record_grabs, storage_or_503
from app.routes import prequiz
from app.routes.prequiz import due_counts, missed_items

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


def _quiz_payload(
    db: Session, user_id: str, lecture: Lecture, quiz: prequiz.Quiz
) -> dict[str, Any] | None:
    """웹 풀이 한 갈래의 진행. 문항이 없으면 `None` — 화면이 그 자리를 안 그린다.

    **예습과 복습이 같은 모양이다.** 갈래는 표만 다르고(`prequiz.Quiz`) 세는 법도
    보여 주는 법도 같다. 갈라 적으면 한쪽에 붙인 손질이 다른 쪽에 안 붙는다.
    """
    item, attempt = quiz.item, quiz.attempt
    item_count = int(
        db.scalar(
            select(func.count()).select_from(item).where(
                item.subject == lecture.subject, item.run_id == lecture.run_id
            )
        )
        or 0
    )
    if not item_count:
        return None
    mine = (
        attempt.user_id == user_id,
        attempt.subject == lecture.subject,
        attempt.run_id == lecture.run_id,
    )
    answered = int(db.scalar(select(func.count()).select_from(attempt).where(*mine)) or 0)
    correct = int(
        db.scalar(select(func.count()).select_from(attempt).where(*mine, attempt.correct.is_(True)))
        or 0
    )
    return {
        "itemCount": item_count,
        "answered": answered,
        "correct": correct,
        # **오늘 낼 카드가 몇 장인가**(2026-09-18, 웹 풀이가 망각곡선으로 돌면서).
        # `answered`는 「이 편을 한 번이라도 훑었나」라서 일정과 다른 것을 말한다 —
        # 다 훑은 편에도 오늘 낼 카드가 있고, 오늘 낼 것이 없는 편도 안 끝난 것이다.
        # 그래서 더하지 않고 나란히 둔다. 세는 곳은 `prequiz.due_counts` 하나다.
        **due_counts(db, user_id, lecture.subject, lecture.run_id, quiz),
        # 다 풀었을 때만 보여 준다. 두 문제 풀고 나온 "놓친 것"은
        # 청취 목표가 아니라 진행 상황일 뿐이다.
        "missed": (
            missed_items(db, user_id, lecture.subject, lecture.run_id, quiz=quiz)
            if answered >= item_count
            else []
        ),
    }


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
    pre_quiz = _quiz_payload(db, user.id, lecture, prequiz.PRE)
    main_quiz = _quiz_payload(db, user.id, lecture, prequiz.MAIN)

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
        # 내 개인 대화. 남의 것은 절대 안 나간다 — 개인 대화 URL은 만든 계정에서만
        # 열리므로 남에게 주면 죽은 링크이고, 무엇을 물었는지만 새어 나간다.
        "myPreview": (
            {"provider": my_preview.provider, "conversationUrl": my_preview.conversation_url}
            if my_preview and my_preview.conversation_url
            else None
        ),
        "prequiz": pre_quiz,
        # **2026-08-31에 생겼고 그 전에 구운 편에는 없다.** 문항이 없으면 `null`이라
        # 화면이 웹 풀이를 아예 안 그린다 — 덱만 있는 편과 같은 자리다.
        "mainquiz": main_quiz,
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
    inline: bool = Query(False, description="참이면 내려받지 않고 브라우저에서 연다."),
    user: CurrentUser = Depends(require_approved_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """누를 때 발급하는 서명 URL. 버킷이 비공개라 이 경로로만 파일이 열린다.

    `inline`은 필기를 읽으려고 누른 경우다. 덱(.apkg)은 받아야 쓰는 것이라
    그대로 첨부로 나간다 — 기본값을 첨부로 둔 이유다.
    """
    lecture = lecture_or_404(db, subject, run_id)
    asset = db.get(Asset, asset_id)
    if asset is None or (asset.subject, asset.run_id) != (lecture.subject, lecture.run_id):
        raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")
    url = storage_or_503().presign_download(
        asset.object_key,
        filename=asset.filename,
        inline=inline,
        content_type=asset.content_type,
    )
    _record_grab(db, user.id, asset)
    return {
        "url": url,
        "expiresIn": get_settings().signed_url_ttl,
        "filename": asset.filename,
    }


def _record_grab(db: Session, user_id: str, asset: Asset) -> None:
    """받아 갔다고 적는다. 캘린더의 채운 점이 이 줄에서 나온다.

    **서명을 낸 뒤에만 적는다.** 저장소가 아직 안 붙었으면 위에서 503으로 끝나고,
    그때는 사용자가 아무것도 못 받았으므로 기록도 남으면 안 된다.

    한 편짜리라 서명과 표시가 같은 자리에 있다 — 누르면 곧바로 파일이 나가서
    둘 사이가 벌어지지 않는다. 모아받기는 그 사이가 몇 분이라 갈라 두었다
    (`routes/bundles.py`). 적는 일 자체는 둘이 같은 함수를 쓴다.
    """
    record_grabs(db, user_id, [(asset.subject, asset.run_id, asset.kind)])


class MyPreviewIn(BaseModel):
    provider: str = "chatgpt"
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
    try:
        selected_provider = valid_provider(payload.provider)
    except ValueError as cause:
        raise HTTPException(status_code=422, detail=str(cause)) from cause
    if not valid_conversation_url(payload.conversation_url, selected_provider):
        raise HTTPException(status_code=422, detail="선택한 AI의 개인 대화 주소가 아닙니다.")
    mine = db.get(UserPreview, (user.id, lecture.subject, lecture.run_id))
    if mine is None:
        mine = UserPreview(user_id=user.id, subject=lecture.subject, run_id=lecture.run_id)
        db.add(mine)
    mine.provider = selected_provider
    mine.conversation_url = payload.conversation_url.strip()
    db.commit()
    return {"provider": mine.provider, "conversationUrl": mine.conversation_url}
