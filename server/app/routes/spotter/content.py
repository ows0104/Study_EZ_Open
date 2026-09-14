"""문항 DB와 사진. **바이트가 서버를 지나는 유일한 자리**와, 그 밖은 전부 서명 URL."""

from __future__ import annotations

import gzip
import hashlib
import mimetypes

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from app.auth import CurrentUser
from app.routes.spotter.common import (
    DEFAULT_SUBJECT,
    MAX_SIGN,
    _db_cache,
    _db_key,
    _image_prefix,
    _safe_name,
    _storage,
    _subject,
    require_spotter,
)

router = APIRouter()


# ── 문항 DB ──────────────────────────────────────────────────────────


@router.get("/subjects/{subject}/db")
def read_subject_db(
    subject: str, request: Request, user: CurrentUser = Depends(require_spotter)
) -> Response:
    """한 과목의 문항 DB 전체. `scripts/upload_subject.py`가 올린 것.

    내용을 서버가 해석하지 않는다. 어떤 문항을 어떤 순서로 낼지는 브라우저가
    정하고, 서버는 후보를 통째로 넘길 뿐이다. 문항 조립을 서버로 올리면 시드를
    바꿀 때마다 왕복이 한 번씩 붙는다.
    """
    subject = _subject(subject)
    cached = _db_cache.get(subject)
    if not cached:
        raw = _storage().get_bytes(_db_key(subject))
        if raw is None:
            raise HTTPException(
                status_code=503,
                detail=f"{subject} 문항 DB가 아직 올라오지 않았습니다. "
                "scripts/upload_subject.py 를 돌려 주세요.",
            )
        cached = {
            "etag": '"' + hashlib.sha1(raw).hexdigest()[:16] + '"',
            "gzipped": gzip.compress(raw, 6),
        }
        _db_cache[subject] = cached

    etag = cached["etag"]
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers={"ETag": etag})
    return Response(
        content=cached["gzipped"],
        media_type="application/json",
        headers={
            "ETag": etag,
            "Content-Encoding": "gzip",
            # 내용이 바뀌면 ETag가 바뀌므로 캐시를 오래 둬도 안전하다.
            # `no-cache`는 "쓰지 말라"가 아니라 "쓰기 전에 물어보라"다.
            "Cache-Control": "private, no-cache",
        },
    )


@router.get("/db", deprecated=True)
def read_db(request: Request, user: CurrentUser = Depends(require_spotter)) -> Response:
    """과목이 하나뿐이던 시절의 주소. 기생충학을 가리킨다.

    **열어 둔 탭을 위한 것이다.** 과목이 다섯이 되면서 주소에 과목이 들어갔는데,
    그 사이에 화면을 열어 둔 사람이 새로고침 없이 다음 문항을 넘기면 여기로
    온다. 한 학기쯤 두고 떼면 된다.
    """
    return read_subject_db(DEFAULT_SUBJECT, request, user)


# ── 사진 ─────────────────────────────────────────────────────────────


class SignIn(BaseModel):
    names: list[str] = Field(default_factory=list)


@router.post("/subjects/{subject}/images/sign")
def sign_subject_images(
    subject: str, payload: SignIn, user: CurrentUser = Depends(require_spotter)
) -> dict[str, dict[str, str]]:
    """이 과목의 사진 서명 URL을 한 번에 받아 간다.

    **문항마다 따로 부르지 않는다.** 40문항이면 왕복이 40번이고, 그중 39번은
    사용자가 다음 문제로 넘어가기를 기다리는 동안 놀고 있는 요청이다. 한 번에
    받아 두면 미리 받기(`new Image().src`)도 그대로 듣는다.

    해부학 과목은 한 판이 700장을 넘길 수 있어서 화면이 커서 앞뒤로 창을 밀며
    나눠 받는다. 전부 한 번에 받으면 응답이 수백 KB가 되고, 그중 대부분은
    사용자가 끝까지 안 가서 안 쓰인다.

    수명은 `STUDYEZ_SIGNED_URL_TTL`(기본 한 시간)이다. 한 판이 그보다 길어지면
    화면이 다시 부른다.
    """
    subject = _subject(subject)
    names = [n for n in dict.fromkeys(payload.names) if n]
    if len(names) > MAX_SIGN:
        raise HTTPException(status_code=400, detail=f"한 번에 {MAX_SIGN}장까지만 됩니다.")
    storage = _storage()
    prefix = _image_prefix(subject)
    urls: dict[str, str] = {}
    for name in names:
        _safe_name(name)
        urls[name] = storage.presign_download(
            f"{prefix}/{name}",
            inline=True,
            content_type=mimetypes.guess_type(name)[0] or "image/jpeg",
        )
    return {"urls": urls}


@router.post("/images/sign", deprecated=True)
def sign_images(
    payload: SignIn, user: CurrentUser = Depends(require_spotter)
) -> dict[str, dict[str, str]]:
    """과목이 하나뿐이던 시절의 주소. `read_db`와 같은 이유로 남겨 둔다."""
    return sign_subject_images(DEFAULT_SUBJECT, payload, user)
