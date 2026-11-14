"""강의별 족보 풀이(jokbo-solve/1). 시간표 칸 하나에 족보 한 벌.

**강의(Lecture)가 아니라 시간표 칸(`TimetableEvent.id`)에 붙는다.** 족보는 올해 필기가
올라오기 전부터 있다 — 필기가 없으면 Lecture 행이 없어서 강의에 붙이면 절반의 칸에서 못 푼다.

족보 문서는 R2다. 문서 한 벌 `jokbo-solve/<eventId>.json`과
그림 `jokbo-solve/figures/<이름>`. 그림은 서명 URL로 나간다(`<img>`라 CORS가 필요 없다).

`audience`가 `admin`이면 관리자에게만 보인다. 해설·교정을 사이트에서 먼저 확인하고 연다.
문서는 러너가 `runner.jokbo_solve upload`로 올리고, 올릴 때 공용 계약으로 다시 검사한다.

오답노트(2026-11-14)는 사람별 기록이라 DB 표 `jokbo_mark`에 둔다. 족보 퀴즈에서 틀리면
「틀림」 표시가 붙고, 사람이 상·중·하로 바꾸거나 뗀다. 오답노트는 강의를 가리지 않고 한 화면이다.
"""

from __future__ import annotations

import io
import json
import re
import time
import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import CurrentUser, require_approved_user, require_runner
from app.database import get_db
from app.models import JokboMark, JokboRound, TimetableEvent
from app.models.base import _now
from app.routes.common import storage_or_503
from studyez_contracts.jokbo import JokboSolveError, validate_lecture

router = APIRouter()
admin_router = APIRouter()

PREFIX = "jokbo-solve"
FIGURE = re.compile(r"^[A-Za-z0-9_.-]+\.(png|jpg|jpeg|gif|webp)$")
FIGURE_TYPES = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "gif": "image/gif", "webp": "image/webp"}
MAX_FIGURE = 5 * 1024 * 1024
Audience = Literal["admin", "all"]


def _doc_key(event_id: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", event_id):
        raise HTTPException(status_code=404, detail="시간표 칸을 찾을 수 없습니다.")
    return f"{PREFIX}/{event_id}.json"


def _figure_key(name: str) -> str:
    if not FIGURE.match(name):
        raise HTTPException(status_code=422, detail="그림 이름이 올바르지 않습니다.")
    return f"{PREFIX}/figures/{name}"


def _load(event_id: str) -> dict[str, Any] | None:
    raw = storage_or_503().get_bytes(_doc_key(event_id))
    return json.loads(raw) if raw else None


# 풀 때마다 문서를 R2에서 다시 읽지 않는다. 올리면 이 프로세스의 것은 바로 비우고,
# 다른 프로세스도 길어야 이만큼 뒤에 새 문서를 본다.
_CACHE_SECONDS = 60.0
_cache: dict[str, tuple[float, dict[str, Any] | None]] = {}


def _load_cached(event_id: str) -> dict[str, Any] | None:
    hit = _cache.get(event_id)
    if hit and time.monotonic() - hit[0] < _CACHE_SECONDS:
        return hit[1]
    stored = _load(event_id)
    _cache[event_id] = (time.monotonic(), stored)
    return stored


def _visible(stored: dict[str, Any] | None, user: CurrentUser) -> dict[str, Any]:
    if stored is None or (stored.get("audience") != "all" and not user.is_admin):
        raise HTTPException(status_code=404, detail="이 강의의 족보가 아직 없습니다.")
    return stored


def summary_of(stored: dict[str, Any]) -> dict[str, Any]:
    doc = stored["doc"]
    sections = doc["sections"]
    return {
        "eventId": doc["lecture"]["eventId"],
        "audience": stored.get("audience", "admin"),
        "items": len(doc["items"]),
        "sameItems": sum(len(s["itemIds"]) for s in sections if s["kind"] == "same"),
        "otherItems": sum(len(s["itemIds"]) for s in sections if s["kind"] == "other"),
        "unknownItems": sum(len(s["itemIds"]) for s in sections if s["kind"] == "unknown"),
    }


@router.get("/jokbo/events/{event_id}/summary")
def jokbo_summary(event_id: str, user: CurrentUser = Depends(require_approved_user)) -> dict[str, Any]:
    return summary_of(_visible(_load(event_id), user))


@router.get("/jokbo/events/{event_id}")
def jokbo_document(event_id: str, user: CurrentUser = Depends(require_approved_user)) -> dict[str, Any]:
    stored = _visible(_load(event_id), user)
    storage = storage_or_503()
    doc = stored["doc"]
    for item in doc["items"]:
        for fig in item.get("figures", []):
            ext = fig["file"].rsplit(".", 1)[-1].lower()
            fig["url"] = storage.presign_download(_figure_key(fig["file"]), inline=True,
                                                  content_type=FIGURE_TYPES.get(ext, "image/png"))
    return {**summary_of(stored), "uploadedAt": stored.get("uploadedAt"), "doc": doc}


@admin_router.put("/jokbo/figures/{name}")
async def put_jokbo_figure(name: str, request: Request, user: CurrentUser = Depends(require_runner)) -> dict[str, Any]:
    key = _figure_key(name)
    body = await request.body()
    if not body or len(body) > MAX_FIGURE:
        raise HTTPException(status_code=413, detail="그림은 5MB 이하만 올릴 수 있습니다.")
    storage = storage_or_503()
    ext = name.rsplit(".", 1)[-1].lower()
    storage.upload_fileobj(io.BytesIO(body), key, content_type=FIGURE_TYPES[ext])
    return {"name": name, "size": len(body)}


@admin_router.get("/jokbo/figures/{name}")
def head_jokbo_figure(name: str, user: CurrentUser = Depends(require_runner)) -> dict[str, Any]:
    head = storage_or_503().head(_figure_key(name))
    return {"name": name, "size": int(head.get("ContentLength", 0)) if head else None}


@admin_router.put("/jokbo/events/{event_id}")
def put_jokbo(
    event_id: str,
    doc: dict[str, Any] = Body(...),
    audience: Audience = Query("admin"),
    user: CurrentUser = Depends(require_runner),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    key = _doc_key(event_id)
    if db.get(TimetableEvent, event_id) is None:
        raise HTTPException(status_code=404, detail="시간표 칸을 찾을 수 없습니다.")
    try:
        validate_lecture(doc)
    except JokboSolveError as cause:
        raise HTTPException(status_code=422, detail=f"jokbo-solve/1 계약 위반: {cause}") from cause
    if doc["lecture"]["eventId"] != event_id:
        raise HTTPException(status_code=422, detail="문서의 eventId가 경로와 다릅니다.")
    storage = storage_or_503()
    missing = sorted({f["file"] for it in doc["items"] for f in it.get("figures", [])
                      if storage.head(_figure_key(f["file"])) is None})
    if missing:
        raise HTTPException(status_code=409, detail={"code": "figures_missing", "files": missing})
    stored = {"audience": audience, "uploadedAt": datetime.now(UTC).isoformat(timespec="seconds"), "doc": doc}
    storage.upload_fileobj(io.BytesIO(json.dumps(stored, ensure_ascii=False).encode("utf-8")), key,
                           content_type="application/json")
    _cache.pop(event_id, None)
    return summary_of(stored)


# ─────────────────────────────────────────────── 오답노트

Band = Literal["high", "mid", "low"]
BAND_ORDER = {"high": 0, "mid": 1, "low": 2}


class AnswerIn(BaseModel):
    result: Literal["correct", "wrong", "ungraded"]


class MarkIn(BaseModel):
    band: Band | None


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return (value if value.tzinfo else value.replace(tzinfo=UTC)).isoformat()


def mark_json(row: JokboMark) -> dict[str, Any]:
    return {
        "itemId": row.item_id,
        "eventId": row.event_id,
        "band": row.band,
        "wrongCount": row.wrong_count,
        "rightCount": row.right_count,
        "lastResult": row.last_result,
        "answeredAt": _iso(row.answered_at),
        "markedAt": _iso(row.marked_at),
    }


def find_item(doc: dict[str, Any], item_id: str) -> dict[str, Any] | None:
    """보이는 문항. 다시 빌드해 다른 해 사본으로 합쳐졌으면 대표 문항이다."""
    for item in doc["items"]:
        if item["id"] == item_id:
            return item
    for item in doc["items"]:
        if any(m.get("id") == item_id for m in item.get("mergedFrom") or []):
            return item
    return None


def _item_for_write(event_id: str, item_id: str, user: CurrentUser) -> None:
    stored = _visible(_load_cached(event_id), user)
    if find_item(stored["doc"], item_id) is None:
        raise HTTPException(status_code=404, detail="족보 문항을 찾을 수 없습니다.")


def _row(db: Session, user: CurrentUser, event_id: str, item_id: str) -> JokboMark:
    row = db.get(JokboMark, (user.id, item_id))
    if row is None:
        row = JokboMark(user_id=user.id, item_id=item_id, event_id=event_id, wrong_count=0, right_count=0)
        db.add(row)
    row.event_id = event_id
    return row


@router.get("/jokbo/marks")
def jokbo_marks(
    event_id: str | None = Query(None, alias="eventId"),
    user: CurrentUser = Depends(require_approved_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    query = select(JokboMark).where(JokboMark.user_id == user.id)
    if event_id:
        query = query.where(JokboMark.event_id == event_id)
    return {"marks": [mark_json(row) for row in db.scalars(query)]}


@router.post("/jokbo/events/{event_id}/items/{item_id}/answer")
def jokbo_answer(
    event_id: str,
    item_id: str,
    body: AnswerIn,
    user: CurrentUser = Depends(require_approved_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """족보 퀴즈에서 한 문제를 풀었다. 틀리면 오답노트에 「틀림」으로 담는다.

    맞혀도 표시는 떼지 않는다 — 떼는 것은 사람이 한다(오답노트에서 다시 보고 판단한다).
    """
    _item_for_write(event_id, item_id, user)
    row = _row(db, user, event_id, item_id)
    now = _now()
    if body.result == "wrong":
        row.wrong_count = (row.wrong_count or 0) + 1
        if row.band != "high":
            row.band = "high"
            row.marked_at = now
    elif body.result == "correct":
        row.right_count = (row.right_count or 0) + 1
    row.last_result = body.result
    row.answered_at = now
    row.updated_at = now
    db.commit()
    return mark_json(row)


@router.put("/jokbo/events/{event_id}/items/{item_id}/mark")
def jokbo_mark(
    event_id: str,
    item_id: str,
    body: MarkIn,
    user: CurrentUser = Depends(require_approved_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """오답노트 표시를 바꾸거나(상·중·하) 뗀다(null). 푼 기록은 그대로 둔다."""
    _item_for_write(event_id, item_id, user)
    row = _row(db, user, event_id, item_id)
    now = _now()
    if row.band != body.band:
        row.band = body.band
        row.marked_at = now if body.band else None
    row.updated_at = now
    db.commit()
    return mark_json(row)


@router.get("/jokbo/wrong-notes")
def jokbo_wrong_notes(
    user: CurrentUser = Depends(require_approved_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """표시가 붙은 족보 문항 전부. 강의를 가리지 않는다.

    순서: 상 → 중 → 하, 그 안은 강의 날짜 → 족보에 실린 순서.
    족보가 내려갔거나(볼 수 없음) 다시 빌드해 문항이 사라졌으면 `missing`으로만 센다.
    """
    rows = list(db.scalars(select(JokboMark).where(JokboMark.user_id == user.id, JokboMark.band.is_not(None))))
    storage = storage_or_503() if rows else None
    docs: dict[str, dict[str, Any] | None] = {}
    out: list[dict[str, Any]] = []
    missing = 0
    seen: set[str] = set()
    for row in rows:
        if row.event_id not in docs:
            stored = _load_cached(row.event_id)
            docs[row.event_id] = stored if stored and (stored.get("audience") == "all" or user.is_admin) else None
        stored = docs[row.event_id]
        item = find_item(stored["doc"], row.item_id) if stored else None
        if item is None:
            missing += 1
            continue
        if item["id"] in seen:
            continue
        seen.add(item["id"])
        doc = stored["doc"]
        section = next((s for s in doc["sections"] if item["id"] in s["itemIds"]), None)
        figures = []
        for fig in item.get("figures", []):
            ext = fig["file"].rsplit(".", 1)[-1].lower()
            figures.append({**fig, "url": storage.presign_download(
                _figure_key(fig["file"]), inline=True, content_type=FIGURE_TYPES.get(ext, "image/png"))})
        lecture = doc["lecture"]
        out.append({
            "mark": mark_json(row),
            "lecture": {"eventId": lecture["eventId"], "number": lecture["number"], "title": lecture["title"],
                        "date": lecture.get("date", "")},
            "kind": section["kind"] if section else "unknown",
            "professors": section["professors"] if section else [],
            "order": doc["items"].index(item),
            "item": {**item, "figures": figures},
        })
    out.sort(key=lambda e: (BAND_ORDER.get(e["mark"]["band"], 9), e["lecture"]["date"], e["order"]))
    for entry in out:
        del entry["order"]
    return {"items": out, "missing": missing}


# ─────────────────────────────────────────────── 회독

MAX_ROUNDS = 30


def jokbo_round_counts(db: Session, user_id: str, event_ids: list[str]) -> dict[str, int]:
    """시간표 칸마다 이 사람의 족보 회독 수. 없는 칸은 빠진다."""
    if not event_ids:
        return {}
    rows = db.execute(
        select(JokboRound.event_id, func.count())
        .where(JokboRound.user_id == user_id, JokboRound.event_id.in_(event_ids))
        .group_by(JokboRound.event_id)
    ).all()
    return {event_id: n for event_id, n in rows}


@router.post("/jokbo/events/{event_id}/rounds")
def add_jokbo_round(
    event_id: str,
    user: CurrentUser = Depends(require_approved_user),
    db: Session = Depends(get_db),
) -> dict[str, int]:
    """족보 1회독. 진입 화면에서 고른 범위를 끝까지 풀고 마무리 화면에 닿으면 웹이 부른다."""
    _visible(_load_cached(event_id), user)
    count = jokbo_round_counts(db, user.id, [event_id]).get(event_id, 0)
    if count >= MAX_ROUNDS:
        raise HTTPException(status_code=409, detail=f"족보 회독은 {MAX_ROUNDS}번까지 기록합니다.")
    db.add(JokboRound(id=uuid.uuid4().hex, user_id=user.id, event_id=event_id))
    db.commit()
    return {"jokboRounds": count + 1}
