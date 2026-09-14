"""올리기. 빌드 스크립트(`require_runner`)만 지난다."""

from __future__ import annotations

import mimetypes
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.auth import CurrentUser, require_runner
from app.routes.spotter.common import (
    _db_cache,
    _db_key,
    _image_prefix,
    _safe_name,
    _storage,
    _subject,
)

router = APIRouter()


# ── 올리기(빌드 스크립트) ────────────────────────────────────────────


class UploadIn(BaseModel):
    """무엇을 올릴 것인가. 키는 서버가 만든다 — 이름만 받는다."""

    names: list[str] = Field(default_factory=list)
    db: bool = False


@router.post("/admin/subjects/{subject}/uploads")
def presign_uploads(
    subject: str, payload: UploadIn, user: CurrentUser = Depends(require_runner)
) -> dict[str, Any]:
    """`scripts/upload_subject.py`가 쓰는 자리. 문항 DB와 사진을 밀어 넣는다.

    **`RUNNER_TOKEN`이거나 관리자 세션이다**(`require_runner`). 올리는 쪽은
    사람이 손으로 돌리는 스크립트지만, 사람이 매번 비밀번호를 치지 않고도
    돌 수 있어야 배포를 자동화할 수 있다. Study_EZ의 로컬 러너가 같은 이유로
    같은 토큰을 쓴다.

    제보함(`/admin/reports`)은 이 갈래를 안 연다 — 저기는 사람이 읽는 화면이고
    토큰이 볼 일이 없다.
    """
    subject = _subject(subject)
    storage = _storage()
    prefix = _image_prefix(subject)
    out: dict[str, Any] = {"images": {}}
    for name in dict.fromkeys(payload.names):
        _safe_name(name)
        out["images"][name] = storage.presign_upload(
            f"{prefix}/{name}",
            content_type=mimetypes.guess_type(name)[0] or "image/jpeg",
        )
    if payload.db:
        out["db"] = storage.presign_upload(_db_key(subject), content_type="application/json")
    return out


@router.get("/admin/subjects/{subject}/manifest")
def manifest(subject: str, user: CurrentUser = Depends(require_runner)) -> dict[str, Any]:
    """지금 R2에 있는 이 과목의 사진과 그 ETag.

    올리는 쪽이 **안 바뀐 것을 건너뛰려고** 본다. 700장 중 두 장을 고쳤을 때
    전부 다시 올리면 수십 MB가 오간다. R2의 ETag는 한 번에 올린 객체에 한해
    내용의 MD5라서, 로컬에서 같은 값을 계산해 견주면 된다.
    """
    subject = _subject(subject)
    storage = _storage()
    if storage.client is None:  # local-test. 디스크에는 ETag가 없다.
        return {"images": {}, "local": True}
    found: dict[str, str] = {}
    token = ""
    while True:
        kwargs: dict[str, Any] = {
            "Bucket": storage.bucket,
            "Prefix": f"{_image_prefix(subject)}/",
        }
        if token:
            kwargs["ContinuationToken"] = token
        page = storage.client.list_objects_v2(**kwargs)
        for item in page.get("Contents", []):
            found[item["Key"].rsplit("/", 1)[-1]] = item.get("ETag", "").strip('"')
        if not page.get("IsTruncated"):
            break
        token = page.get("NextContinuationToken", "")
    return {"images": found, "local": False}


@router.post("/admin/subjects/{subject}/db/refresh")
def refresh_db_cache(subject: str, user: CurrentUser = Depends(require_runner)) -> dict[str, str]:
    """방금 올린 문항 DB를 이 인스턴스가 다시 읽게 한다.

    **인스턴스가 여럿이면 이 호출은 그중 하나만 비운다.** Cloud Run은 요청을
    아무 컨테이너에나 보내므로 나머지는 낡은 것을 들고 있다가 새로 뜰 때
    바뀐다. 완전한 해결은 키에 판번호를 붙이는 것인데, 그러면 화면이 어느
    판을 볼지 정하는 값이 하나 더 생긴다. 사용자가 한 학년이고 빌드가 드물어
    지금은 이 쪽이 낫다 — 늦어도 다음 콜드 스타트에는 맞춰진다.
    """
    _db_cache.pop(_subject(subject), None)
    return {"status": "cleared", "subject": subject}
