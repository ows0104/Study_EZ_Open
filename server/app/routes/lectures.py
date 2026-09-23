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
    JOB_KINDS,
    JOB_PRE,
    PREVIEW_OPEN_KINDS,
    Asset,
    Lecture,
    PrequizJob,
    Preview,
    RunMeta,
    RunnerBeat,
    TimetableEvent,
    UserPreview,
)
from app.preview_links import conversation_url as valid_conversation_url
from app.preview_links import provider as valid_provider
from app.routes.common import (
    lecture_or_404,
    record_grabs,
    record_preview_open,
    storage_or_503,
)
from app.routes import cards, prequiz
from app.routes.prequiz import due_counts, missed_items
from app.routes.prequiz_jobs import RUNNER_NAME, watch_row, watch_runner_row

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
        # 사이드 패널의 「카드 고치기」가 적는 수(2026-09-23). 답까지 든 카드 목록은
        # 여기 안 싣는다 — 고치는 자리가 `…/cards/{kind}` 로 따로 읽는다.
        payload["cardReview"] = cards.review_counts(db, lecture)
    return payload


@router.get("/lectures/{subject}/{run_id}/deck-job")
def lecture_deck_job(
    subject: str,
    run_id: str,
    kind: str = JOB_PRE,
    user: CurrentUser = Depends(require_approved_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """덱을 지금 만들고 있는가. **학생이 보는 쪽이다.**

    2026-09-21 관리자 지시 — 관리자가 아닌 사람도 몇 단계에 몇 분 남았는지를
    보게 해달라. 관리자가 보는 것(`GET /api/admin/…/prequiz-job`)과 **같은 표를
    읽지만 주는 칸이 다르다**(`watch_row`) — 저쪽은 누가 눌렀고 어느 일꾼이
    잡았고 왜 실패했는지까지 든다. 그래서 경로를 같이 쓰지 않고 하나 더 세웠다 —
    `/api/admin` 아래의 것을 학생에게 열어 주는 것과는 다른 일이다.

    **강의 상세(`GET /api/lectures/…`)에 실어 보내지 않는다.** 한 편에 15분이라
    진행은 **다시 읽어야 보이는 값**이고, 상세를 10초마다 다시 읽게 하면 풀이
    진행과 문항까지 같이 딸려온다.

    러너 상태를 같이 준다. **일감이 안 움직이는 이유가 둘이라 가른다** —
    노트북이 꺼져 있거나, 켜져 있는데 차례를 기다리거나. 학생이 그 둘에 대해
    할 수 있는 일은 같지만, 「곧 됩니다」와 「멈춰 있습니다」를 섞어 말하면 그 줄을
    믿을 이유가 없어진다.
    """
    if kind not in JOB_KINDS:
        raise HTTPException(400, f"모르는 일감 종류입니다: {kind}")
    lecture = lecture_or_404(db, subject, run_id)
    job = db.scalars(
        select(PrequizJob)
        .where(
            PrequizJob.subject == lecture.subject,
            PrequizJob.run_id == lecture.run_id,
            PrequizJob.kind == kind,
        )
        .order_by(PrequizJob.created_at.desc())
    ).first()
    return {"job": watch_row(job), "runner": watch_runner_row(db.get(RunnerBeat, RUNNER_NAME))}


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


class PreviewOpenIn(BaseModel):
    #: share = 반이 같이 읽는 기본 링크 · mine = 내 대화. `PREVIEW_OPEN_KINDS` 와 같다.
    kind: str


@router.post("/lectures/{subject}/{run_id}/preview-open", status_code=204)
def post_preview_open(
    subject: str,
    run_id: str,
    payload: PreviewOpenIn,
    user: CurrentUser = Depends(require_approved_user),
    db: Session = Depends(get_db),
) -> None:
    """예습 링크를 눌렀다. **화면이 알려 주지 않으면 서버는 모른다.**

    `share_url` 도 `conversationUrl` 도 AI 서비스의 주소라, 누르면 그 길로 가고
    여기를 안 지난다. 그래서 누르는 자리가 한 줄 보낸다 — 2026-09-19 관리자
    질문(「기본링크도 얼마나 클릭했는지 알 수는 없나?」)의 답이 이것이다.

    **본문이 없다(204).** 화면은 이 응답을 안 기다리고 링크를 연다. 여기서 무엇이
    잘못되든 링크는 열려야 한다.

    없는 갈래는 조용히 버린다(`record_preview_open`). 화면이 오타를 보내도 링크를
    막지 않기 위해서다 — 대신 그 줄은 아무 데도 안 남는다.
    """
    lecture = lecture_or_404(db, subject, run_id)
    if payload.kind in PREVIEW_OPEN_KINDS:
        record_preview_open(db, user.id, lecture.subject, lecture.run_id, payload.kind)


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
