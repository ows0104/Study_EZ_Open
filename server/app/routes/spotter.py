"""기생충학 땡시 연습(Spotter_Quiz)이 쓰는 경로.

**문은 로그인 하나다.** Study_EZ의 경로가 사람의 승인을 기다리는 것과 갈린다 —
저기서 나가는 것은 남이 만든 강의 필기라 「이 학년 학생인가」를 사람이 확인해야
하지만, 여기 있는 것은 우리가 만든 문항과 실습 정리본 사진이다. 가입하면 열린다.

그 차이는 이 파일이 아니라 `models.APP_POLICY`에 한 줄로 적혀 있다
(`spotter: auto`). 여기서는 `require_spotter`를 지나는 것이 전부이고, 세 번째
앱도 정책 한 줄만 고르면 같은 자리에 붙는다.

계정은 같다. 같은 Supabase, 같은 `profile` 표를 쓰므로 두 앱에 각각 가입할
필요가 없다. 승인(`is_approved`)은 Study_EZ 쪽 화면에서만 의미를 갖는다.

R2 키는 `spotter/` 아래에 모은다. Study_EZ의 강의 자료와 같은 버킷을 쓰되
접두사로 갈라 둔다 — 버킷을 따로 두면 자격증명이 한 벌 더 늘고, 그것이 이
분리가 막아 주는 것보다 크다.
"""

from __future__ import annotations

import gzip
import hashlib
import mimetypes
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.auth import CurrentUser, require_admin, require_app, require_runner
from app.database import get_db
from app.models import (
    APP_SPOTTER,
    SPOTTER_RECORD_KEEP,
    SPOTTER_REPORT_KINDS,
    SPOTTER_REPORT_OPEN,
    SPOTTER_REPORT_RESOLVED,
    SPOTTER_REPORT_STATUSES,
    Profile,
    SpotterRecord,
    SpotterReport,
    SpotterWrong,
)
from app.storage import ObjectStorage, StorageNotConfigured

router = APIRouter(prefix="/spotter", tags=["spotter"])

# 이 앱의 문. `APP_POLICY[APP_SPOTTER]`가 `auto`라 로그인하면 그 자리에서
# 권한이 나온다. Study_EZ가 `manual`이라 사람을 기다리는 것과 갈리는
# 지점이고, 이 줄 하나가 그 차이의 전부다.
require_spotter = require_app(APP_SPOTTER)

PREFIX = "spotter"
DB_KEY = f"{PREFIX}/quiz_db.json"
IMAGE_PREFIX = f"{PREFIX}/images"

# 한 번에 서명해 줄 사진의 수. 한 세트가 최대 60문항이고 다시보기에서 같은
# 세트를 또 쓰므로 그보다 넉넉히 잡는다. 상한이 있는 것은 이 경로가 로그인만
# 지나기 때문이다 — 없으면 한 번의 요청으로 555장을 통째로 받아 갈 수 있다.
MAX_SIGN = 80

# 문항 DB. 인스턴스마다 한 벌 들고 있는다.
#
# **바이트가 서버를 지나는 유일한 자리다.** 서명 URL로 내보내면 주소가 매번
# 달라져 브라우저 캐시가 안 듣고, 5.4MB짜리를 접속할 때마다 새로 받는다.
# gzip하면 0.24MB고 ETag가 붙으므로 두 번째 접속부터는 304로 끝난다.
_db_cache: dict[str, Any] = {"etag": "", "gzipped": b""}


def _storage() -> ObjectStorage:
    try:
        return ObjectStorage()
    except StorageNotConfigured as exc:
        raise HTTPException(status_code=503, detail="자료 저장소가 아직 준비되지 않았습니다.") from exc


def _iso(value: datetime) -> str:
    """시각 하나. **오프셋을 반드시 붙인다.**

    화면이 `new Date(...)`로 읽는데, 오프셋이 없으면 브라우저가 그것을 **현지
    시각**으로 해석한다. 우리는 UTC로 저장하므로 그대로 두면 기록이 아홉 시간
    어긋나 보인다. Postgres는 `timezone=True` 칼럼에서 오프셋을 돌려주지만
    sqlite(로컬 테스트)는 떼어 버려서, 두 곳이 다르게 도는 것을 여기서 막는다.
    """
    return (value if value.tzinfo else value.replace(tzinfo=UTC)).isoformat()


def _safe_name(name: str) -> str:
    """사진 이름 한 칸. 키를 만들기 전에 반드시 지난다.

    `..`나 `/`가 든 이름을 그대로 이으면 접두사 밖을 가리키는 키가 되고,
    그러면 이 경로로 Study_EZ의 강의 필기가 새어 나간다. 같은 버킷을 쓰는
    대가이므로 여기서 한 번에 막는다.
    """
    if not name or "/" in name or "\\" in name or name.startswith("."):
        raise HTTPException(status_code=400, detail=f"사진 이름이 올바르지 않습니다: {name}")
    return name


# ── 문항 DB ──────────────────────────────────────────────────────────


@router.get("/db")
def read_db(request: Request, user: CurrentUser = Depends(require_spotter)) -> Response:
    """문항 DB 전체. `scripts/build_web.py`가 굽고 `scripts/upload_web.py`가 올린 것.

    내용을 서버가 해석하지 않는다. 어떤 40문항을 뽑을지는 브라우저가 정하고
    (가중 표집·중복 회피·순서), 서버는 후보를 통째로 넘길 뿐이다. 문항 조립을
    서버로 올리면 시드를 바꿀 때마다 왕복이 한 번씩 붙는다.
    """
    if not _db_cache["gzipped"]:
        raw = _storage().get_bytes(DB_KEY)
        if raw is None:
            raise HTTPException(
                status_code=503,
                detail="문항 DB가 아직 올라오지 않았습니다. scripts/upload_web.py 를 돌려 주세요.",
            )
        _db_cache["etag"] = '"' + hashlib.sha1(raw).hexdigest()[:16] + '"'
        _db_cache["gzipped"] = gzip.compress(raw, 6)

    etag = _db_cache["etag"]
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers={"ETag": etag})
    return Response(
        content=_db_cache["gzipped"],
        media_type="application/json",
        headers={
            "ETag": etag,
            "Content-Encoding": "gzip",
            # 내용이 바뀌면 ETag가 바뀌므로 캐시를 오래 둬도 안전하다.
            # `no-cache`는 "쓰지 말라"가 아니라 "쓰기 전에 물어보라"다.
            "Cache-Control": "private, no-cache",
        },
    )


# ── 사진 ─────────────────────────────────────────────────────────────


class SignIn(BaseModel):
    names: list[str] = Field(default_factory=list)


@router.post("/images/sign")
def sign_images(
    payload: SignIn, user: CurrentUser = Depends(require_spotter)
) -> dict[str, dict[str, str]]:
    """세트가 쓰는 사진의 서명 URL을 한 번에 받아 간다.

    **문항마다 따로 부르지 않는다.** 40문항이면 왕복이 40번이고, 그중 39번은
    사용자가 다음 문제로 넘어가기를 기다리는 동안 놀고 있는 요청이다. 세트를
    만든 직후에 한 번에 받아 두면 미리 받기(`new Image().src`)도 그대로 듣는다.

    수명은 `STUDYEZ_SIGNED_URL_TTL`(기본 한 시간)이다. 한 판이 그보다 길어지는
    일은 드물고, 길어지면 화면이 다시 부른다.
    """
    names = [n for n in dict.fromkeys(payload.names) if n]
    if len(names) > MAX_SIGN:
        raise HTTPException(status_code=400, detail=f"한 번에 {MAX_SIGN}장까지만 됩니다.")
    storage = _storage()
    urls: dict[str, str] = {}
    for name in names:
        _safe_name(name)
        urls[name] = storage.presign_download(
            f"{IMAGE_PREFIX}/{name}",
            inline=True,
            content_type=mimetypes.guess_type(name)[0] or "image/jpeg",
        )
    return {"urls": urls}


# ── 내 기록 ──────────────────────────────────────────────────────────


def _state(db: Session, user_id: str) -> dict[str, Any]:
    records = db.scalars(
        select(SpotterRecord)
        .where(SpotterRecord.user_id == user_id)
        .order_by(SpotterRecord.created_at.desc(), SpotterRecord.id.desc())
        .limit(SPOTTER_RECORD_KEEP)
    ).all()
    wrong = db.scalars(select(SpotterWrong.question_id).where(SpotterWrong.user_id == user_id)).all()
    return {
        "records": [
            {
                "id": row.id,
                "mode": row.mode,
                "score": row.score,
                "total": row.total,
                "at": _iso(row.created_at),
            }
            for row in records
        ],
        "wrong": list(wrong),
    }


@router.get("/state")
def read_state(
    user: CurrentUser = Depends(require_spotter), db: Session = Depends(get_db)
) -> dict[str, Any]:
    """기록과 오답노트. 로그인하면 어느 기기에서든 같은 것이 나온다."""
    return _state(db, user.id)


class FinishIn(BaseModel):
    mode: str = "exam"
    score: int = 0
    total: int = 0
    # 이번 판에서 틀린 것과 맞힌 것. 맞힌 것을 같이 보내는 이유는 오답노트에서
    # **빼기 위해서**다 — 맞혔다는 사실은 이 목록에만 있다.
    wrong: list[str] = Field(default_factory=list)
    right: list[str] = Field(default_factory=list)


@router.post("/finish")
def finish(
    payload: FinishIn,
    user: CurrentUser = Depends(require_spotter),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """한 판이 끝났다. 기록을 남기고 오답노트를 고친다.

    **한 번의 왕복이다.** 화면이 채점하는 순간 하는 일이 「기록 추가·오답
    추가·정답 제거」 셋인데, 경로를 셋으로 가르면 중간에 하나가 실패했을 때
    오답노트만 반쯤 갱신된 상태가 남는다.
    """
    total = max(0, payload.total)
    if total:
        db.add(
            SpotterRecord(
                user_id=user.id,
                mode="study" if payload.mode == "study" else "exam",
                score=max(0, min(payload.score, total)),
                total=total,
            )
        )

    wrong = {q for q in payload.wrong if q}
    right = {q for q in payload.right if q} - wrong
    if right:
        db.execute(
            delete(SpotterWrong).where(
                SpotterWrong.user_id == user.id, SpotterWrong.question_id.in_(right)
            )
        )
    if wrong:
        have = set(
            db.scalars(
                select(SpotterWrong.question_id).where(
                    SpotterWrong.user_id == user.id, SpotterWrong.question_id.in_(wrong)
                )
            ).all()
        )
        for qid in wrong - have:
            db.add(SpotterWrong(user_id=user.id, question_id=qid))

    # 기록은 최근 것만 든다. 오래된 줄은 화면이 안 그리고, 그대로 두면 한 사람이
    # 학기 내내 푼 판이 전부 쌓인다.
    stale = db.scalars(
        select(SpotterRecord.id)
        .where(SpotterRecord.user_id == user.id)
        .order_by(SpotterRecord.created_at.desc(), SpotterRecord.id.desc())
        .offset(SPOTTER_RECORD_KEEP)
    ).all()
    if stale:
        db.execute(delete(SpotterRecord).where(SpotterRecord.id.in_(stale)))

    db.commit()
    return _state(db, user.id)


class MergeIn(BaseModel):
    """이 브라우저에 쌓여 있던 것. 로그인 직후 한 번만 올라온다."""

    wrong: list[str] = Field(default_factory=list)


@router.post("/state/merge")
def merge_state(
    payload: MergeIn,
    user: CurrentUser = Depends(require_spotter),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """로그인 전에 이 브라우저에 쌓인 오답노트를 계정으로 옮긴다.

    **더하기만 한다.** 로그인 없이 쓰던 사람이 계정을 만들 때 그동안의 오답이
    사라지지 않게 하는 것이 전부다. 빼기까지 하면 기기 하나에 남은 오래된
    목록이 다른 기기에서 맞힌 것을 되살린다.

    기록(`records`)은 안 옮긴다 — 날짜와 점수뿐이라 옮길 값이 크지 않고,
    브라우저마다 다른 시각 표기가 그대로 섞여 들어온다.
    """
    incoming = {q for q in payload.wrong if q}
    if incoming:
        have = set(
            db.scalars(
                select(SpotterWrong.question_id).where(
                    SpotterWrong.user_id == user.id, SpotterWrong.question_id.in_(incoming)
                )
            ).all()
        )
        for qid in incoming - have:
            db.add(SpotterWrong(user_id=user.id, question_id=qid))
        db.commit()
    return _state(db, user.id)


# ── 문항 신고 ────────────────────────────────────────────────────────


class ReportIn(BaseModel):
    question_id: str = Field(alias="questionId")
    kind: str = "other"
    note: str = ""
    stem: str = ""
    answer: str = ""
    image: str = ""

    model_config = {"populate_by_name": True}


def _report_row(row: SpotterReport, email: str = "") -> dict[str, Any]:
    return {
        "id": row.id,
        "questionId": row.question_id,
        "kind": row.kind,
        "note": row.note,
        "stem": row.stem,
        "answer": row.answer,
        "image": row.image,
        "status": row.status,
        "adminNote": row.admin_note,
        "at": _iso(row.created_at),
        "email": email,
    }


@router.post("/reports")
def create_report(
    payload: ReportIn,
    user: CurrentUser = Depends(require_spotter),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """「이 문항 이상해요」.

    문항이 자동 생성이라(오답 보기도 마스터 표에서 뽑는다) 사람이 걸러 주는
    자리가 없으면 틀린 문항이 조용히 남는다. 화면 아래 작은 글씨로 "오류가
    있을 수 있습니다"라고 적어 두는 것과 그 자리에서 신고를 받는 것은 다르다.

    같은 사람이 같은 문항을 다시 신고하면 **줄을 고쳐 쓴다.** 목록에서 세는
    것은 몇 명이 걸렸는가지 몇 번 눌렀는가가 아니다.
    """
    qid = payload.question_id.strip()
    if not qid:
        raise HTTPException(status_code=400, detail="문항을 알 수 없습니다.")

    row = db.scalar(
        select(SpotterReport).where(
            SpotterReport.user_id == user.id, SpotterReport.question_id == qid
        )
    )
    if row is None:
        row = SpotterReport(user_id=user.id, question_id=qid)
        db.add(row)
    row.kind = payload.kind if payload.kind in SPOTTER_REPORT_KINDS else "other"
    row.note = payload.note.strip()[:2000]
    # 신고 당시의 문면. 지금의 문항이 아니다 — 모델의 설명을 보라.
    row.stem = payload.stem.strip()[:1000]
    row.answer = payload.answer.strip()[:500]
    row.image = payload.image.strip()[:300]
    # 다시 신고했다는 것은 아직 안 고쳐졌다는 뜻이다. 닫혀 있었으면 연다.
    row.status = SPOTTER_REPORT_OPEN
    db.commit()
    return _report_row(row, user.email)


@router.get("/reports/mine")
def list_my_reports(
    user: CurrentUser = Depends(require_spotter), db: Session = Depends(get_db)
) -> dict[str, Any]:
    """내가 낸 신고. 화면이 「신고함」 표시를 다는 데 쓴다."""
    rows = db.scalars(
        select(SpotterReport)
        .where(SpotterReport.user_id == user.id)
        .order_by(SpotterReport.created_at.desc())
    ).all()
    return {"reports": [_report_row(row, user.email) for row in rows]}


# ── 신고함(관리자) ───────────────────────────────────────────────────


@router.get("/admin/reports")
def list_reports(
    status: str = "", user: CurrentUser = Depends(require_admin), db: Session = Depends(get_db)
) -> dict[str, Any]:
    """들어온 신고 전부. **문항으로 묶어서** 낸다.

    먼저 볼 것은 여럿이 걸린 문항이다. 한 사람이 잘못 읽은 것과 열 명이 같은
    자리에서 멈춘 것은 다른 일이고, 시간이 한정되면 뒤쪽을 먼저 고쳐야 한다.
    시각순으로 늘어놓으면 그 구분이 목록에서 사라진다.
    """
    query = select(SpotterReport).order_by(SpotterReport.created_at.desc())
    if status in SPOTTER_REPORT_STATUSES:
        query = query.where(SpotterReport.status == status)
    rows = db.scalars(query).all()

    user_ids = {row.user_id for row in rows}
    emails = {
        profile.id: profile.email
        for profile in db.scalars(select(Profile).where(Profile.id.in_(user_ids or {""}))).all()
    }

    groups: dict[str, dict[str, Any]] = {}
    for row in rows:
        group = groups.setdefault(
            row.question_id, {"questionId": row.question_id, "open": 0, "reports": []}
        )
        group["reports"].append(_report_row(row, emails.get(row.user_id, "")))
        if row.status == SPOTTER_REPORT_OPEN:
            group["open"] += 1

    ordered = sorted(
        groups.values(), key=lambda g: (-g["open"], -len(g["reports"]), g["reports"][0]["at"])
    )
    return {"groups": ordered, "total": len(rows)}


class ReportPatch(BaseModel):
    status: str = ""
    admin_note: str = Field(default="", alias="adminNote")

    model_config = {"populate_by_name": True}


@router.patch("/admin/reports/{report_id}")
def update_report(
    report_id: int,
    payload: ReportPatch,
    user: CurrentUser = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    row = db.get(SpotterReport, report_id)
    if row is None:
        raise HTTPException(status_code=404, detail="없는 신고입니다.")
    if payload.status:
        if payload.status not in SPOTTER_REPORT_STATUSES:
            raise HTTPException(status_code=400, detail="상태 값이 올바르지 않습니다.")
        row.status = payload.status
    row.admin_note = payload.admin_note.strip()[:2000]
    db.commit()
    return _report_row(row)


@router.post("/admin/reports/{question_id}/close")
def close_question(
    question_id: str,
    user: CurrentUser = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, int]:
    """이 문항에 걸린 신고를 한꺼번에 닫는다.

    고치는 단위가 문항이라서 닫는 단위도 문항이다. 한 문항에 다섯 명이
    걸렸으면 다섯 줄을 따로 누르게 하는 것이 이상하다.
    """
    rows = db.scalars(
        select(SpotterReport).where(
            SpotterReport.question_id == question_id,
            SpotterReport.status == SPOTTER_REPORT_OPEN,
        )
    ).all()
    for row in rows:
        row.status = SPOTTER_REPORT_RESOLVED
    db.commit()
    return {"closed": len(rows)}


# ── 올리기(빌드 스크립트) ────────────────────────────────────────────


class UploadIn(BaseModel):
    """무엇을 올릴 것인가. 키는 서버가 만든다 — 이름만 받는다."""

    names: list[str] = Field(default_factory=list)
    db: bool = False


@router.post("/admin/uploads")
def presign_uploads(payload: UploadIn, user: CurrentUser = Depends(require_runner)) -> dict[str, Any]:
    """`scripts/upload_web.py`가 쓰는 자리. 문항 DB와 사진을 밀어 넣는다.

    **`RUNNER_TOKEN`이거나 관리자 세션이다**(`require_runner`). 올리는 쪽은
    사람이 손으로 돌리는 스크립트지만, 사람이 매번 비밀번호를 치지 않고도
    돌 수 있어야 배포를 자동화할 수 있다. Study_EZ의 로컬 러너가 같은 이유로
    같은 토큰을 쓴다.

    신고함(`/admin/reports`)은 이 갈래를 안 연다 — 저기는 사람이 읽는 화면이고
    토큰이 볼 일이 없다.
    """
    storage = _storage()
    out: dict[str, Any] = {"images": {}}
    for name in dict.fromkeys(payload.names):
        _safe_name(name)
        out["images"][name] = storage.presign_upload(
            f"{IMAGE_PREFIX}/{name}",
            content_type=mimetypes.guess_type(name)[0] or "image/jpeg",
        )
    if payload.db:
        out["db"] = storage.presign_upload(DB_KEY, content_type="application/json")
    return out


@router.get("/admin/manifest")
def manifest(user: CurrentUser = Depends(require_runner)) -> dict[str, Any]:
    """지금 R2에 있는 사진과 그 ETag.

    올리는 쪽이 **안 바뀐 것을 건너뛰려고** 본다. 555장 중 두 장을 고쳤을 때
    전부 다시 올리면 30MB가 오간다. R2의 ETag는 한 번에 올린 객체에 한해
    내용의 MD5라서, 로컬에서 같은 값을 계산해 견주면 된다.
    """
    storage = _storage()
    if storage.client is None:  # local-test. 디스크에는 ETag가 없다.
        return {"images": {}, "local": True}
    found: dict[str, str] = {}
    token = ""
    while True:
        kwargs: dict[str, Any] = {"Bucket": storage.bucket, "Prefix": f"{IMAGE_PREFIX}/"}
        if token:
            kwargs["ContinuationToken"] = token
        page = storage.client.list_objects_v2(**kwargs)
        for item in page.get("Contents", []):
            found[item["Key"].rsplit("/", 1)[-1]] = item.get("ETag", "").strip('"')
        if not page.get("IsTruncated"):
            break
        token = page.get("NextContinuationToken", "")
    return {"images": found, "local": False}


@router.post("/admin/db/refresh")
def refresh_db_cache(user: CurrentUser = Depends(require_runner)) -> dict[str, str]:
    """방금 올린 문항 DB를 이 인스턴스가 다시 읽게 한다.

    **인스턴스가 여럿이면 이 호출은 그중 하나만 비운다.** Cloud Run은 요청을
    아무 컨테이너에나 보내므로 나머지는 낡은 것을 들고 있다가 새로 뜰 때
    바뀐다. 완전한 해결은 키에 판번호를 붙이는 것인데, 그러면 화면이 어느
    판을 볼지 정하는 값이 하나 더 생긴다. 사용자가 한 학년이고 빌드가 드물어
    지금은 이 쪽이 낫다 — 늦어도 다음 콜드 스타트에는 맞춰진다.
    """
    _db_cache["etag"] = ""
    _db_cache["gzipped"] = b""
    return {"status": "cleared"}
