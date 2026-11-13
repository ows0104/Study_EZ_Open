"""강의별 족보 풀이(jokbo-solve/1). 시간표 칸 하나에 족보 한 벌.

**강의(Lecture)가 아니라 시간표 칸(`TimetableEvent.id`)에 붙는다.** 족보는 올해 필기가
올라오기 전부터 있다 — 필기가 없으면 Lecture 행이 없어서 강의에 붙이면 절반의 칸에서 못 푼다.

저장은 R2다(DB 표를 새로 만들지 않는다). 문서 한 벌 `jokbo-solve/<eventId>.json`과
그림 `jokbo-solve/figures/<이름>`. 그림은 서명 URL로 나간다(`<img>`라 CORS가 필요 없다).

`audience`가 `admin`이면 관리자에게만 보인다. 해설·교정을 사이트에서 먼저 확인하고 연다.
문서는 러너가 `runner.jokbo_solve upload`로 올리고, 올릴 때 공용 계약으로 다시 검사한다.
"""

from __future__ import annotations

import io
import json
import re
from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.auth import CurrentUser, require_approved_user, require_runner
from app.database import get_db
from app.models import TimetableEvent
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
    return summary_of(stored)
