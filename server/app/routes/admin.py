"""로컬 러너가 밀어 넣는 곳, 그리고 `/admin` 화면이 읽는 곳.

파일은 **서명 URL로 R2에 직접 올린다.** 서버를 거치지 않는 이유는 Cloud Run의
요청 본문 상한(32MB)이 강의록 PDF보다 작기 때문이다. 서버는 키를 정하고 올라온
것을 확인만 한다.

키는 `(subject, run_id, kind, filename)`으로 결정된다. 같은 파일을 다시 올리면
같은 자리에 덮이고, 그래서 러너가 중간에 끊겨도 처음부터 다시 돌리면 된다.
"""

from __future__ import annotations

import uuid
from datetime import date as Date, datetime, timezone
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
    CHECKLIST_ITEMS,
    JOB_DONE,
    JOB_FAILED,
    JOB_OPEN,
    JOB_QUEUED,
    JOB_RUNNING,
    Asset,
    CourseAlias,
    Lecture,
    LectureWaive,
    PreItem,
    PrequizJob,
    Preview,
    Profile,
    RunMeta,
    RunnerBeat,
    TimetableEvent,
)
from app.naming import nfc, object_key, slide_no_from_filename
from app.routes.common import lecture_or_404, storage_or_503

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
    storage = storage_or_503()
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
    storage = storage_or_503()
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
    """예습 카드 한 장. 자유회상이라 보기가 없다 — 채점은 본인이 한다."""

    id: str
    qtype: Literal["basic", "cloze", "ox"]
    stem: str
    answer: str
    focus: str = ""
    card_type: str = ""
    exam_hit: bool = False
    slide_no: int | None = None
    source_type: str = "lecture"
    source_anchor: str = ""
    explanation: str = ""
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
        if not item.answer.strip():
            # 답이 없는 카드는 펴 봐야 빈 칸이 뜬다. 그 자리에서 막는다.
            raise HTTPException(status_code=422, detail=f"{item.id}: 답이 비어 있습니다.")
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
                answer=item.answer,
                focus=item.focus,
                card_type=item.card_type,
                exam_hit=item.exam_hit,
                slide_no=item.slide_no,
                source_type=item.source_type,
                source_anchor=item.source_anchor,
                explanation=item.explanation,
                flags=item.flags,
            )
        )
    db.commit()
    return {"itemCount": len(payload.items)}


# ---------------------------------------------------------------- 예습 링크


class PreviewIn(BaseModel):
    """준 것만 바꾼다.

    확장이 두 링크를 따로 들고 온다 — 대화 주소는 전송 직후에, 공유 주소는 답이
    끝난 뒤에 생긴다. 안 준 칸까지 빈 문자열로 덮으면 나중에 온 쪽이 먼저 온 쪽을
    지운다. 러너는 둘을 같이 보내므로 그쪽 동작은 그대로다.
    """

    provider: str = "chatgpt"
    share_url: str | None = Field(default=None, alias="shareUrl")
    conversation_url: str | None = Field(default=None, alias="conversationUrl")

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
    if payload.share_url is not None:
        preview.share_url = payload.share_url.strip()
    if payload.conversation_url is not None:
        preview.conversation_url = payload.conversation_url.strip()
    db.commit()
    return {"shareUrl": preview.share_url, "hasConversationUrl": bool(preview.conversation_url)}


@router.get("/previews")
def list_previews(
    user: CurrentUser = Depends(require_runner),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """저장된 예습 링크 전부. **여기만 방향이 반대다.**

    다른 모든 것은 로컬이 만들어 서버로 민다. 예습 링크만 서버에서 로컬로
    가는데, 예습을 하는 것은 사람이고 사람은 `/admin` 화면에서 저장하기
    때문이다. 로컬은 이 목록을 보고 그 강의의 Pre-Quiz를 만든다.

    `/overview`로 갈음할 수 없다 — 그쪽은 `require_admin`이라 Supabase 세션이
    있어야 하고, 러너는 사람이 아니라 토큰이다.

    `conversation_url`은 내보내지 않는다. 퀴즈를 만들 때 쓰는 것은 `share_url`
    뿐이고, `/c/` 주소는 관리자 화면 밖으로 나갈 이유가 없다.
    """
    counts = {
        (subject, run_id): count
        for subject, run_id, count in db.execute(
            select(PreItem.subject, PreItem.run_id, func.count()).group_by(
                PreItem.subject, PreItem.run_id
            )
        )
    }
    joined = db.execute(
        select(Preview, Lecture)
        .join(
            Lecture,
            (Lecture.subject == Preview.subject) & (Lecture.run_id == Preview.run_id),
        )
        .where(Preview.share_url != "")
    )
    rows = [
        {
            "subject": preview.subject,
            "runId": preview.run_id,
            "date": lecture.date.isoformat(),
            "title": lecture.title,
            "provider": preview.provider,
            "shareUrl": preview.share_url,
            "updatedAt": preview.updated_at.isoformat() if preview.updated_at else "",
            # 이미 올라간 Pre-Quiz 문항 수. 러너가 사람에게 적어 주는 값이고,
            # 만들지 말지의 판정은 로컬 산출물이 한다.
            "preItemCount": counts.get((preview.subject, preview.run_id), 0),
        }
        for preview, lecture in joined
    ]
    rows.sort(key=lambda row: (row["date"], row["runId"]))
    return {"previews": rows}


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


# ---------------------------------------------------------------- 체크리스트


class WaiveIn(BaseModel):
    item: str
    waived: bool = True
    note: str = ""


@router.put("/lectures/{subject}/{run_id}/waive")
def set_waive(
    subject: str,
    run_id: str,
    payload: WaiveIn,
    user: CurrentUser = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """체크 칸 하나를 "해당 없음"으로 닫거나 되돌린다.

    신설 강의에는 작년 필기가 없다. 그런 칸을 영영 미완으로 두면 화면이 미완으로
    가득 차고, 그러면 정말 밀린 강의가 안 보인다.
    """
    if payload.item not in CHECKLIST_ITEMS:
        raise HTTPException(status_code=400, detail=f"모르는 체크 항목입니다: {payload.item}")
    lecture = lecture_or_404(db, subject, run_id)
    key = (lecture.subject, lecture.run_id, payload.item)
    row = db.get(LectureWaive, key)
    if payload.waived:
        if row is None:
            row = LectureWaive(subject=lecture.subject, run_id=lecture.run_id, item=payload.item)
            db.add(row)
        row.note = payload.note
    elif row is not None:
        db.delete(row)
    db.commit()
    return {"item": payload.item, "waived": payload.waived}


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


def _checklist(kinds: set[str], preview: Preview | None, waived: set[str]) -> dict[str, str]:
    """다섯 칸의 상태. 올라온 것이 닫아 둔 것을 이긴다.

    닫아 둔 칸에 나중에 자료가 올라오면 `done`으로 돌아온다 — 자료가 있는데
    "해당 없음"으로 보이면 화면이 거짓말을 하는 것이다. `lecture_waive` 줄은
    그대로 두고 표시만 양보한다.
    """
    done = {
        "notes_prev": "notes_prev" in kinds,
        "preview": bool(preview and preview.share_url),
        "pre_apkg": "pre_apkg" in kinds,
        "notes_current": "notes_current" in kinds,
        "main_apkg": "main_apkg" in kinds,
    }
    return {
        item: "done" if done[item] else "waived" if item in waived else "todo"
        for item in CHECKLIST_ITEMS
    }


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
    # 편마다 **가장 최근** 일감 하나. 끝난 것도 보여 준다 — 실패한 채로 사라지면
    # 화면이 "아직 아무도 안 눌렀다"와 같은 모양이 된다.
    jobs: dict[tuple[str, str], PrequizJob] = {}
    for job in db.scalars(select(PrequizJob).order_by(PrequizJob.created_at)):
        jobs[(job.subject, job.run_id)] = job
    waived: dict[tuple[str, str], set[str]] = {}
    for row in db.scalars(select(LectureWaive)):
        waived.setdefault((row.subject, row.run_id), set()).add(row.item)
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
                # 관리자가 채우는 다섯 칸. `done`은 올라왔다, `waived`는 이 강의엔
                # 해당 없다고 닫았다, `todo`는 아직 관리자 몫으로 남았다.
                "checklist": _checklist(
                    kinds.get(key, set()), previews.get(key), waived.get(key, set())
                ),
                "preItemCount": item_counts.get(key, 0),
                "prequizJob": _job_row(jobs.get(key)),
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
        "runner": _runner_row(db.get(RunnerBeat, RUNNER_NAME)),
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


# ---------------------------------------------------------------- 계정 승인


@router.get("/users")
def list_users(
    user: CurrentUser = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """가입한 사람 전부. 승인 안 된 사람이 먼저 온다 — 할 일이 위에 있어야 한다."""
    profiles = db.scalars(select(Profile)).all()
    profiles.sort(key=lambda row: (row.is_approved, row.email.lower()))
    return [
        {
            "id": row.id,
            "email": row.email,
            "isAdmin": row.is_admin,
            "isApproved": row.is_approved,
            "createdAt": row.created_at.isoformat() if row.created_at else None,
        }
        for row in profiles
    ]


class ApprovalIn(BaseModel):
    is_approved: bool = Field(alias="isApproved")

    model_config = {"populate_by_name": True}


@router.put("/users/{user_id}/approval")
def set_approval(
    user_id: str,
    payload: ApprovalIn,
    user: CurrentUser = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    profile = db.get(Profile, user_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="계정을 찾을 수 없습니다.")
    # 관리자가 자기 승인을 내리면 그 길로 /admin에서 잠긴다. 되돌릴 사람이
    # 자기뿐일 수 있으므로 아예 막는다.
    if profile.id == user.id and not payload.is_approved:
        raise HTTPException(status_code=400, detail="자기 승인은 내릴 수 없습니다.")
    profile.is_approved = payload.is_approved
    db.commit()
    return {"id": profile.id, "isApproved": profile.is_approved}


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


# ---------------------------------------------------------------- 예습 일감

# 러너는 지금 한 대뿐이다. 여러 대가 되면 이름을 나눠야 하는데, 그때는 일감을
# 집어 가는 쪽도 같이 고쳐야 하므로 상수 하나로 묶어 둔다.
RUNNER_NAME = "local"


def _job_row(job: PrequizJob | None) -> dict[str, Any] | None:
    if job is None:
        return None
    return {
        "id": job.id,
        "subject": job.subject,
        "runId": job.run_id,
        "state": job.state,
        "stage": job.stage,
        "message": job.message,
        "requestedBy": job.requested_by,
        "createdAt": job.created_at.isoformat() if job.created_at else "",
        "updatedAt": job.updated_at.isoformat() if job.updated_at else "",
    }


def _runner_row(beat: RunnerBeat | None) -> dict[str, Any] | None:
    if beat is None:
        return None
    return {
        "lastSeen": beat.last_seen.isoformat() if beat.last_seen else "",
        "busy": beat.busy,
        "note": beat.note,
    }


def _touch_runner(db: Session, *, busy: bool, note: str) -> None:
    """러너가 살아 있다고 적는다. **러너가 말을 걸 때마다 지나가는 자리다.**

    물어보는 것(`claim`)만으로는 모자란다. 한 편을 집어 가면 러너는 15분 동안
    `claim`을 안 부르므로(`agent.tick`이 `handle` 안에 머문다), 진행을 적는
    `PUT`도 여기를 지나야 한다. 안 그러면 2분 뒤부터 화면이 멀쩡히 만드는 중인
    러너를 「안 붙어 있습니다」라고 말한다.
    """
    beat = db.get(RunnerBeat, RUNNER_NAME)
    if beat is None:
        beat = RunnerBeat(name=RUNNER_NAME)
        db.add(beat)
    beat.busy = busy
    beat.note = note[:500]
    beat.last_seen = datetime.now(timezone.utc)


@router.post("/lectures/{subject}/{run_id}/prequiz-job")
def request_prequiz(
    subject: str,
    run_id: str,
    user: CurrentUser = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """「Pre-Quiz 만들기」. 일감 한 줄을 적고, 만드는 것은 러너가 한다.

    **두 번 눌러도 두 번 만들지 않는다.** 열려 있는 일감이 있으면 그것을 그대로
    돌려준다 — 15분짜리 일이라 사람이 반응이 없다고 다시 누르는 일이 잦다.

    예습 링크가 없으면 거절한다. Pre-Quiz는 그 대화를 들고 들어가는지 묻는
    것이므로, 링크 없이 만들면 다른 물건이 된다.
    """
    lecture = lecture_or_404(db, subject, run_id)
    preview = db.get(Preview, (lecture.subject, lecture.run_id))
    if preview is None or not preview.share_url:
        raise HTTPException(400, "예습 링크를 먼저 저장하세요. Pre-Quiz는 그 대화로 만듭니다.")

    open_job = db.scalars(
        select(PrequizJob)
        .where(
            PrequizJob.subject == lecture.subject,
            PrequizJob.run_id == lecture.run_id,
            PrequizJob.state.in_(tuple(JOB_OPEN)),
        )
        .order_by(PrequizJob.created_at.desc())
    ).first()
    if open_job is not None:
        return {"job": _job_row(open_job), "created": False}

    job = PrequizJob(
        subject=lecture.subject,
        run_id=lecture.run_id,
        state=JOB_QUEUED,
        stage="러너를 기다리는 중",
        requested_by=user.email,
    )
    db.add(job)
    db.commit()
    return {"job": _job_row(job), "created": True}


@router.get("/lectures/{subject}/{run_id}/prequiz-job")
def lecture_prequiz_job(
    subject: str,
    run_id: str,
    user: CurrentUser = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """이 강의의 가장 최근 일감. 없으면 `null`.

    캘린더 패널이 「Pre-Quiz 덱 — 아직 없습니다」 자리에서 부른다. `/overview`로
    갈음할 수 있지만 그쪽은 학기 전체를 그리는 응답이라, 패널 하나 여는 값으로는
    비싸다.

    러너 상태를 같이 준다. **일감이 안 움직이는 이유가 둘이라 가른다** — 러너가
    안 떠 있거나, 떠 있는데 앞의 편을 만드는 중이거나.
    """
    lecture = lecture_or_404(db, subject, run_id)
    job = db.scalars(
        select(PrequizJob)
        .where(PrequizJob.subject == lecture.subject, PrequizJob.run_id == lecture.run_id)
        .order_by(PrequizJob.created_at.desc())
    ).first()
    return {"job": _job_row(job), "runner": _runner_row(db.get(RunnerBeat, RUNNER_NAME))}


@router.post("/prequiz-jobs/claim")
def claim_prequiz_job(
    user: CurrentUser = Depends(require_runner),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """러너가 일감 하나를 집어 간다. 없으면 `null`. **박동도 여기서 찍는다.**

    한 번에 하나만 준다. 한 편이 이미 빈 세션 넷을 띄우므로 겹쳐 돌릴 자리가
    아니다(`studyez.watch.build`와 같은 이유).

    이미 `running`인 것이 있으면 새 일감을 주지 않고 그것을 돌려준다 — 러너가
    끊겼다 붙었을 때 하던 일을 이어 잡으라는 뜻이다.
    """
    running = db.scalars(
        select(PrequizJob).where(PrequizJob.state == JOB_RUNNING).order_by(PrequizJob.created_at)
    ).first()
    job = running or db.scalars(
        select(PrequizJob).where(PrequizJob.state == JOB_QUEUED).order_by(PrequizJob.created_at)
    ).first()

    if job is not None and job.state == JOB_QUEUED:
        job.state = JOB_RUNNING
        job.stage = "시작"
        job.started_at = datetime.now(timezone.utc)

    _touch_runner(db, busy=job is not None,
                  note=f"{job.subject}/{job.run_id}" if job is not None else "")
    db.commit()
    return {"job": _job_row(job)}


class JobUpdate(BaseModel):
    state: Literal["running", "done", "failed"] | None = None
    stage: str | None = None
    message: str | None = None

    model_config = {"populate_by_name": True}


@router.put("/prequiz-jobs/{job_id}")
def update_prequiz_job(
    job_id: int,
    payload: JobUpdate,
    user: CurrentUser = Depends(require_runner),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """러너가 진행을 적는다. 끝난 일감은 다시 열지 않는다.

    **몸이 비어 있어도 된다.** 그때는 아무것도 안 바꾸고 박동만 찍는다 — 한
    단계가 2분 넘게 이어지는 동안 러너가 죽은 것으로 보이지 않게.
    """
    job = db.get(PrequizJob, job_id)
    if job is None:
        raise HTTPException(404, "그런 일감이 없습니다.")
    if job.state in (JOB_DONE, JOB_FAILED):
        # 끝난 뒤에 늦게 도착한 갱신. 조용히 무시하는 편이 안전하다 —
        # 다시 열면 화면이 끝난 편을 도는 중으로 보여 준다.
        return {"job": _job_row(job), "applied": False}

    if payload.stage is not None:
        job.stage = payload.stage[:500]
    if payload.message is not None:
        job.message = payload.message[:2000]
    if payload.state is not None:
        job.state = payload.state
        if payload.state in (JOB_DONE, JOB_FAILED):
            job.finished_at = datetime.now(timezone.utc)

    # 이 호출 자체가 박동이다(`_touch_runner`). 빈 몸으로 와도 마찬가지 —
    # 러너는 단계가 안 바뀌어도 여기를 두드려 살아 있다고 알린다.
    finished = job.state in (JOB_DONE, JOB_FAILED)
    _touch_runner(db, busy=not finished,
                  note="" if finished else f"{job.subject}/{job.run_id}")
    db.commit()
    return {"job": _job_row(job), "applied": True}


@router.get("/prequiz-jobs")
def list_prequiz_jobs(
    user: CurrentUser = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """최근 일감. `/overview`가 편마다 하나씩 들고 있지만, 흐름을 보려면 여기다."""
    jobs = db.scalars(select(PrequizJob).order_by(PrequizJob.created_at.desc()).limit(50)).all()
    return {
        "jobs": [_job_row(job) for job in jobs],
        "runner": _runner_row(db.get(RunnerBeat, RUNNER_NAME)),
    }
