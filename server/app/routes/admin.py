"""로컬 러너가 밀어 넣는 곳, 그리고 `/admin` 화면이 읽는 곳.

파일은 **서명 URL로 R2에 직접 올린다.** 서버를 거치지 않는 이유는 Cloud Run의
요청 본문 상한(32MB)이 강의록 PDF보다 작기 때문이다. 서버는 키를 정하고 올라온
것을 확인만 한다.

키는 `(subject, run_id, kind, filename)`으로 결정된다. 같은 파일을 다시 올리면
같은 자리에 덮이고, 그래서 러너가 중간에 끊겨도 처음부터 다시 돌리면 된다.
"""

from __future__ import annotations

import uuid
from datetime import date as Date, datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.auth import CurrentUser, require_admin, require_runner
from app.config import get_settings
from app.database import get_db
from app.matching import relink
from app.models import (
    ASSET_KINDS,
    Asset,
    CourseAlias,
    Lecture,
    PreItem,
    Preview,
    RunMeta,
    TimetableEvent,
)
from app.naming import nfc, object_key, slide_no_from_filename
from app.routes.common import lecture_or_404
from app.storage import ObjectStorage

router = APIRouter()

# 강의당 하나뿐인 것들. 새 판이 올라오면 앞의 것을 지운다 — 러너가 최신 판만
# 고르므로 서버에 v1과 v3이 같이 남아 있을 이유가 없다.
SINGULAR_KINDS = frozenset({"notes_current", "notes_prev", "main_apkg", "pre_apkg"})


# ---------------------------------------------------------------- 강의 등록


class LectureIn(BaseModel):
    subject: str
    run_id: str = Field(alias="runId")
    uid: str
    date: Date
    slot: int
    slot_end: int | None = Field(default=None, alias="slotEnd")
    start_time: str = Field(alias="startTime")
    title: str
    professors: list[str] = Field(default_factory=list)
    author: str = ""
    version: int | None = None

    model_config = {"populate_by_name": True}


@router.post("/lectures")
def upsert_lectures(
    payload: list[LectureIn],
    user: CurrentUser = Depends(require_runner),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    linked = 0
    for row in payload:
        subject = nfc(row.subject)
        lecture = db.get(Lecture, (subject, row.run_id))
        if lecture is None:
            lecture = Lecture(subject=subject, run_id=row.run_id)
            db.add(lecture)
        lecture.uid = nfc(row.uid)
        lecture.date = row.date
        lecture.slot = row.slot
        lecture.slot_end = row.slot_end if row.slot_end is not None else row.slot
        lecture.start_time = row.start_time
        lecture.title = nfc(row.title)
        lecture.professors = [nfc(name) for name in row.professors]
        lecture.author = nfc(row.author)
        lecture.version = row.version
        db.flush()
        relink(db, lecture)
        if lecture.timetable_event_id:
            linked += 1
    db.commit()
    # 붙지 않은 강의는 조용히 넘기지 않는다. `/admin`의 매칭 확인이 이 수를 본다.
    return {"received": len(payload), "linked": linked, "unlinked": len(payload) - linked}


# ---------------------------------------------------------------- 파일


class FileIn(BaseModel):
    kind: str
    filename: str
    size_bytes: int = Field(default=0, alias="sizeBytes")
    content_type: str = Field(default="application/octet-stream", alias="contentType")

    model_config = {"populate_by_name": True}


def _validate(files: list[FileIn]) -> None:
    settings = get_settings()
    limit = settings.max_upload_mb * 1024 * 1024
    for item in files:
        if item.kind not in ASSET_KINDS:
            raise HTTPException(
                status_code=422,
                detail=f"'{item.kind}'는 산출물 계약에 없는 종류입니다. 계약을 먼저 고쳐 주세요.",
            )
        if item.size_bytes > limit:
            raise HTTPException(
                status_code=413, detail=f"파일은 {settings.max_upload_mb}MB 이하만 올릴 수 있습니다."
            )


@router.post("/lectures/{subject}/{run_id}/uploads")
def presign_uploads(
    subject: str,
    run_id: str,
    files: list[FileIn],
    user: CurrentUser = Depends(require_runner),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    lecture = lecture_or_404(db, subject, run_id)
    _validate(files)
    storage = ObjectStorage()
    return {
        "files": [
            {
                "kind": item.kind,
                "filename": nfc(item.filename),
                "objectKey": (key := object_key(lecture.subject, lecture.run_id, item.kind, item.filename)),
                "uploadUrl": storage.presign_upload(key, content_type=item.content_type),
            }
            for item in files
        ],
        "expiresIn": 900,
    }


@router.post("/lectures/{subject}/{run_id}/uploads/complete")
def complete_uploads(
    subject: str,
    run_id: str,
    files: list[FileIn],
    user: CurrentUser = Depends(require_runner),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    lecture = lecture_or_404(db, subject, run_id)
    _validate(files)
    storage = ObjectStorage()
    stored: list[str] = []
    missing: list[str] = []

    for item in files:
        filename = nfc(item.filename)
        key = object_key(lecture.subject, lecture.run_id, item.kind, filename)
        head = storage.head(key)
        if head is None:
            missing.append(filename)
            continue

        if item.kind in SINGULAR_KINDS:
            for old in db.scalars(
                select(Asset).where(
                    Asset.subject == lecture.subject,
                    Asset.run_id == lecture.run_id,
                    Asset.kind == item.kind,
                    Asset.object_key != key,
                )
            ):
                storage.delete(old.object_key)
                db.delete(old)

        asset = db.scalar(select(Asset).where(Asset.object_key == key))
        if asset is None:
            asset = Asset(id=str(uuid.uuid4()), subject=lecture.subject, run_id=lecture.run_id)
            db.add(asset)
        asset.kind = item.kind
        asset.filename = filename
        asset.object_key = key
        asset.size_bytes = int(head.get("ContentLength", 0))
        asset.content_type = item.content_type
        asset.slide_no = slide_no_from_filename(filename) if item.kind == "media" else None
        stored.append(filename)

    db.commit()
    # 올라오지 않은 파일을 성공으로 세지 않는다. 러너가 이 목록을 보고 다시 민다.
    return {"stored": len(stored), "missing": missing}


# ---------------------------------------------------------------- 산출물 JSON


@router.put("/lectures/{subject}/{run_id}/run-meta/{quiz_kind}")
def put_run_meta(
    subject: str,
    run_id: str,
    quiz_kind: Literal["main", "pre"],
    payload: dict[str, Any],
    user: CurrentUser = Depends(require_runner),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    lecture = lecture_or_404(db, subject, run_id)
    meta = db.get(RunMeta, (lecture.subject, lecture.run_id, quiz_kind))
    if meta is None:
        meta = RunMeta(subject=lecture.subject, run_id=lecture.run_id, quiz_kind=quiz_kind)
        db.add(meta)
    meta.payload = payload
    # 목록 화면이 payload를 펼치지 않고도 경고할 수 있게 꺼내 둔다.
    meta.review_flagged = int(payload.get("review_flagged") or 0)
    meta.slides_unused = len(payload.get("slides_unused") or [])
    meta.item_count = int(payload.get("item_count") or 0)
    built_at = payload.get("built_at")
    try:
        meta.built_at = datetime.fromisoformat(built_at) if built_at else None
    except (TypeError, ValueError):
        meta.built_at = None
    db.commit()
    return {"reviewFlagged": meta.review_flagged, "slidesUnused": meta.slides_unused}


class PreItemIn(BaseModel):
    id: str
    qtype: Literal["mcq", "short", "ox"]
    stem: str
    choices: list[str] | None = None
    answer: str
    focus: str = "core"
    exam_hit: bool = False
    slide_no: int | None = None
    source_type: str = "lecture"
    source_anchor: str = ""
    explanation: str = ""
    objective_id: str = ""
    retrieval_target: str = ""
    flags: list[str] = Field(default_factory=list)


class PreItemsIn(BaseModel):
    lecture_id: str = ""
    items: list[PreItemIn]


@router.put("/lectures/{subject}/{run_id}/pre-items")
def put_pre_items(
    subject: str,
    run_id: str,
    payload: PreItemsIn,
    user: CurrentUser = Depends(require_runner),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """`pre_items.final.json` 통째로. 부분 갱신이 아니라 교체다."""
    lecture = lecture_or_404(db, subject, run_id)
    for item in payload.items:
        if item.qtype == "mcq" and len(item.choices or []) != 5:
            raise HTTPException(
                status_code=422,
                detail=f"{item.id}: mcq의 보기는 정확히 5개여야 합니다.",
            )
    db.execute(
        delete(PreItem).where(PreItem.subject == lecture.subject, PreItem.run_id == lecture.run_id)
    )
    for order, item in enumerate(payload.items):
        db.add(
            PreItem(
                subject=lecture.subject,
                run_id=lecture.run_id,
                item_id=item.id,
                ord=order,
                qtype=item.qtype,
                stem=item.stem,
                choices=item.choices,
                answer=item.answer,
                focus=item.focus,
                exam_hit=item.exam_hit,
                slide_no=item.slide_no,
                source_type=item.source_type,
                source_anchor=item.source_anchor,
                explanation=item.explanation,
                objective_id=item.objective_id,
                retrieval_target=item.retrieval_target,
                flags=item.flags,
            )
        )
    db.commit()
    return {"itemCount": len(payload.items)}


# ---------------------------------------------------------------- 예습 링크


class PreviewIn(BaseModel):
    provider: str = "chatgpt"
    share_url: str = Field(default="", alias="shareUrl")
    conversation_url: str = Field(default="", alias="conversationUrl")

    model_config = {"populate_by_name": True}


@router.put("/lectures/{subject}/{run_id}/preview")
def put_preview(
    subject: str,
    run_id: str,
    payload: PreviewIn,
    user: CurrentUser = Depends(require_runner),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    lecture = lecture_or_404(db, subject, run_id)
    preview = db.get(Preview, (lecture.subject, lecture.run_id))
    if preview is None:
        preview = Preview(subject=lecture.subject, run_id=lecture.run_id)
        db.add(preview)
    preview.provider = payload.provider
    preview.share_url = payload.share_url.strip()
    preview.conversation_url = payload.conversation_url.strip()
    db.commit()
    return {"shareUrl": preview.share_url, "hasConversationUrl": bool(preview.conversation_url)}


# ---------------------------------------------------------------- 매칭


class MatchIn(BaseModel):
    timetable_event_id: str | None = Field(default=None, alias="timetableEventId")
    confirmed: bool = True

    model_config = {"populate_by_name": True}


@router.put("/lectures/{subject}/{run_id}/match")
def set_match(
    subject: str,
    run_id: str,
    payload: MatchIn,
    user: CurrentUser = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    lecture = lecture_or_404(db, subject, run_id)
    if payload.timetable_event_id and db.get(TimetableEvent, payload.timetable_event_id) is None:
        raise HTTPException(status_code=404, detail="시간표 칸을 찾을 수 없습니다.")
    lecture.timetable_event_id = payload.timetable_event_id
    lecture.match_confirmed = payload.confirmed
    db.commit()
    return {"timetableEventId": lecture.timetable_event_id, "confirmed": lecture.match_confirmed}


class CourseAliasIn(BaseModel):
    course_key: str = Field(alias="courseKey")
    course: str = ""
    subject: str

    model_config = {"populate_by_name": True}


@router.put("/course-aliases")
def put_course_aliases(
    payload: list[CourseAliasIn],
    user: CurrentUser = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, int]:
    """과목을 이어 준다. 비운 것은 지운다 — 잘못 이은 것을 되돌릴 길이 있어야 한다."""
    for row in payload:
        alias = db.get(CourseAlias, row.course_key)
        subject = nfc(row.subject)
        if not subject:
            if alias is not None:
                db.delete(alias)
            continue
        if alias is None:
            alias = CourseAlias(course_key=row.course_key)
            db.add(alias)
        alias.course = nfc(row.course)
        alias.subject = subject
    db.commit()

    # 별칭이 바뀌면 좁혀지는 후보가 달라진다. 확인하지 않은 매칭만 다시 계산한다.
    for lecture in db.scalars(select(Lecture)):
        relink(db, lecture)
    db.commit()
    return {"saved": len(payload)}


# ---------------------------------------------------------------- /admin 화면


@router.get("/overview")
def overview(
    user: CurrentUser = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """매칭 확인 · 업로드 현황 · 예습 링크를 한 번에.

    강의 수가 학기당 300편 안쪽이라 통째로 내려도 된다. 페이지를 나누면 "어디가
    비어 있는가"를 한눈에 보는 화면의 목적이 흐려진다.
    """
    lectures = db.scalars(select(Lecture).order_by(Lecture.date, Lecture.slot, Lecture.subject)).all()
    events = {event.id: event for event in db.scalars(select(TimetableEvent))}

    kinds: dict[tuple[str, str], set[str]] = {}
    for subject, run_id, kind in db.execute(
        select(Asset.subject, Asset.run_id, Asset.kind).group_by(Asset.subject, Asset.run_id, Asset.kind)
    ):
        kinds.setdefault((subject, run_id), set()).add(kind)

    item_counts = {
        (subject, run_id): count
        for subject, run_id, count in db.execute(
            select(PreItem.subject, PreItem.run_id, func.count()).group_by(PreItem.subject, PreItem.run_id)
        )
    }
    previews = {(row.subject, row.run_id): row for row in db.scalars(select(Preview))}
    metas: dict[tuple[str, str], dict[str, RunMeta]] = {}
    for meta in db.scalars(select(RunMeta)):
        metas.setdefault((meta.subject, meta.run_id), {})[meta.quiz_kind] = meta

    rows = []
    for lecture in lectures:
        key = (lecture.subject, lecture.run_id)
        event = events.get(lecture.timetable_event_id) if lecture.timetable_event_id else None
        preview = previews.get(key)
        meta = metas.get(key, {})
        rows.append(
            {
                "subject": lecture.subject,
                "runId": lecture.run_id,
                "date": lecture.date.isoformat(),
                "slot": lecture.slot,
                "title": lecture.title,
                "professors": lecture.professors,
                "author": lecture.author,
                "version": lecture.version,
                "match": {
                    "timetableEventId": lecture.timetable_event_id,
                    "confirmed": lecture.match_confirmed,
                    "eventTitle": event.title if event else None,
                    "eventDetails": event.details if event else None,
                },
                "has": {kind: kind in kinds.get(key, set()) for kind in sorted(ASSET_KINDS)},
                "preItemCount": item_counts.get(key, 0),
                "preview": (
                    {
                        "shareUrl": preview.share_url,
                        "conversationUrl": preview.conversation_url,
                        "provider": preview.provider,
                    }
                    if preview
                    else None
                ),
                # 배포해도 되는가. 0이 아니면 사람이 카드 뒷면 경고 박스를 봐야 한다.
                "runMeta": {
                    quiz_kind: {
                        "reviewFlagged": value.review_flagged,
                        "slidesUnused": value.slides_unused,
                        "itemCount": value.item_count,
                        "builtAt": value.built_at.isoformat() if value.built_at else None,
                    }
                    for quiz_kind, value in meta.items()
                },
            }
        )

    return {
        "lectures": rows,
        "courseAliases": [
            {"courseKey": row.course_key, "course": row.course, "subject": row.subject}
            for row in db.scalars(select(CourseAlias))
        ],
        "timetableCourses": timetable_courses(events.values()),
        "subjects": sorted({lecture.subject for lecture in lectures}),
    }


# 과목으로 볼 만한 최소 횟수. 이 아래는 한 번짜리 특강·행사이지 과목이 아니다.
# 걸러 내지 않으면 "휴식", "개교기념일", "수업소개 김범석"까지 이어 줄 목록에
# 올라와 80줄이 되고, 그러면 정작 이어야 할 다섯 과목이 묻힌다.
MIN_COURSE_SESSIONS = 5


def timetable_courses(events) -> list[dict[str, Any]]:
    """이어 줄 만한 과목만. 표기가 흔들려도 한 줄로 묶는다.

    실물에 "면역의 기초"와 "면역의기초"가 같이 있다. 표기 그대로 묶으면 한
    과목이 두 줄로 갈라지고 별칭도 반쪽만 걸린다.
    """
    counts: dict[str, dict[str, int]] = {}
    for event in events:
        if event.category not in ("lecture", "practice") or not event.course_key:
            continue
        spellings = counts.setdefault(event.course_key, {})
        spellings[event.course] = spellings.get(event.course, 0) + 1

    courses = [
        {
            "courseKey": course_key,
            # 가장 흔한 표기를 대표로 보여 준다.
            "course": max(spellings.items(), key=lambda item: item[1])[0],
            "sessions": sum(spellings.values()),
        }
        for course_key, spellings in counts.items()
        if sum(spellings.values()) >= MIN_COURSE_SESSIONS
    ]
    return sorted(courses, key=lambda item: -item["sessions"])


@router.get("/timetable-events")
def timetable_events(
    date: Date,
    user: CurrentUser = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """손으로 매칭을 고칠 때 고를 후보."""
    events = db.scalars(
        select(TimetableEvent)
        .where(TimetableEvent.date == date)
        .order_by(TimetableEvent.start_time, TimetableEvent.title)
    ).all()
    return [
        {
            "id": event.id,
            "startTime": event.start_time,
            "slot": event.slot,
            "title": event.title,
            "details": event.details,
            "professor": event.professor,
            "category": event.category,
        }
        for event in events
    ]
