"""진리탐구 게시판. 제보가 모이면 글타래가 서고, 닫히면 격리가 풀린다."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import CurrentUser, require_admin
from app.database import get_db
from app.models import (
    SPOTTER_ALERT_MIN,
    SPOTTER_COMMENT_MAX,
    SPOTTER_REPORT_OPEN,
    SPOTTER_REPORT_RESOLVED,
    SPOTTER_REPORT_STATUSES,
    SPOTTER_THREAD_IMAGE,
    SPOTTER_THREAD_KINDS,
    SPOTTER_THREAD_QUESTION,
    Profile,
    SpotterComment,
    SpotterReport,
    SpotterThread,
)
from app.routes.spotter.common import (
    _hot_images,
    _hot_questions,
    _image_names,
    _iso,
    require_spotter,
)

router = APIRouter()


# ── 진리탐구 게시판 ──────────────────────────────────────────────────
#
# **글타래는 사람이 세우지 않는다.** 제보가 선을 넘으면 서버가 세운다.
# 아무 이야기나 하는 자리가 아니라 여럿이 같은 자리에서 멈춘 문항만 모이는
# 자리라서다 — 무엇을 올릴지 사람이 고르기 시작하면 판정이 두 벌이 된다.


def _display_name(email: str) -> str:
    """게시판에 적는 이름. **이메일을 통째로 걸지 않는다.**

    제보함은 관리자만 보는 화면이라 주소를 그대로 냈지만, 게시판은 로그인한
    사람 모두가 읽는다. 같은 학년이라 앞부분만으로 서로 알아보고, 주소는
    안 걸린다.
    """
    return email.split("@")[0] if email else "알 수 없음"


def ensure_threads(db: Session) -> None:
    """선을 넘은 것마다 글타래가 서 있게 한다. **여러 번 불러도 같다.**

    제보가 들어올 때마다 표 전체를 다시 센다. 학년 하나가 쓰는 앱이라 줄이
    많아야 몇백이고, 그 대신 「어디서 세는가」가 한 군데로 남는다 — 들어오는
    길마다 따로 세면 늦게 들어온 제보가 글타래를 못 세우는 자리가 생긴다.

    **읽는 자리(/threads·/flagged)에서도 부른다.** 지켜야 하는 것은
    「선을 넘은 것에는 글타래가 있다」인데, 이것은 제보가 들어올 때만 깨지는
    것이 아니라 **선이 움직일 때도 깨진다**. 선을 2에서 1로 내렸을 때 이미
    들어와 있던 1인 제보들이 그랬다 — 그 문항에 누가 한 번 더 제보하기
    전까지는 게시판에 오르지 못한 채 제보함에만 남아서, 관리자만 아는 것이
    되었다. 읽을 때 맞추면 선을 옮기는 것만으로 밀린 것이 따라 올라온다.

    **닫힌 글타래는 다시 안 연다.** 고쳐 놓고 닫았는데 옛 제보가 그대로
    열려 있다고 해서 되살아나면 닫을 방법이 없다.
    """
    rows = db.scalars(select(SpotterReport)).all()
    have = {(row.kind, row.subject) for row in db.scalars(select(SpotterThread)).all()}

    made = False
    for question_id in _hot_questions(rows):
        if (SPOTTER_THREAD_QUESTION, question_id) in have:
            continue
        latest = max(
            (r for r in rows if r.question_id == question_id), key=lambda r: r.created_at
        )
        db.add(
            SpotterThread(
                kind=SPOTTER_THREAD_QUESTION,
                subject=question_id,
                stem=latest.stem,
                answer=latest.answer,
                images=", ".join(_image_names(latest)),
            )
        )
        made = True

    for spot in _hot_images(rows):
        if (SPOTTER_THREAD_IMAGE, spot["image"]) in have:
            continue
        db.add(
            SpotterThread(
                kind=SPOTTER_THREAD_IMAGE,
                subject=spot["image"],
                # 사진 글타래의 문면은 문항 하나의 것이 아니다. 걸린 문항이
                # 여럿이라 화면이 그 목록을 따로 그린다.
                stem="",
                answer="",
                images=spot["image"],
            )
        )
        made = True

    if made:
        db.commit()


def _thread_reports(thread: SpotterThread, rows: list[SpotterReport]) -> list[SpotterReport]:
    """이 글타래가 안고 있는 제보들.

    문항 글타래는 그 문항에 걸린 것, 사진 글타래는 **그 사진을 든 문항 전부**의
    것이다. 사진이 흐리다는 이야기는 문항마다 흩어져 들어오므로, 한자리에
    모아 놓지 않으면 게시판에서도 같은 이야기가 세 군데로 갈린다.
    """
    if thread.kind == SPOTTER_THREAD_IMAGE:
        return [row for row in rows if thread.subject in _image_names(row)]
    return [row for row in rows if row.question_id == thread.subject]


def _thread_row(thread: SpotterThread, rows: list[SpotterReport], comments: int) -> dict[str, Any]:
    mine = _thread_reports(thread, rows)
    return {
        "kind": thread.kind,
        "subject": thread.subject,
        "stem": thread.stem,
        "answer": thread.answer,
        "images": [name.strip() for name in thread.images.split(",") if name.strip()],
        "status": thread.status,
        "verdict": thread.verdict,
        "at": _iso(thread.created_at),
        "reports": len({row.user_id for row in mine}),
        "questionIds": sorted({row.question_id for row in mine}),
        # 목록은 수만 쓴다. 글타래 하나를 열면 `comments`에 줄들이 실려 온다 —
        # 같은 이름에 수와 목록이 섞이면 화면이 어느 쪽인지 헷갈린다.
        "commentCount": comments,
    }


def _comment_counts(db: Session) -> dict[int, int]:
    counts: dict[int, int] = {}
    for row in db.scalars(select(SpotterComment).where(SpotterComment.deleted.is_(False))).all():
        counts[row.thread_id] = counts.get(row.thread_id, 0) + 1
    return counts


def _names(db: Session, user_ids: set[str]) -> dict[str, str]:
    profiles = db.scalars(select(Profile).where(Profile.id.in_(user_ids or {""}))).all()
    return {profile.id: _display_name(profile.email) for profile in profiles}


def _find_thread(db: Session, kind: str, subject: str) -> SpotterThread:
    if kind not in SPOTTER_THREAD_KINDS:
        raise HTTPException(status_code=400, detail="없는 갈래입니다.")
    thread = db.scalar(
        select(SpotterThread).where(SpotterThread.kind == kind, SpotterThread.subject == subject)
    )
    if thread is None:
        raise HTTPException(status_code=404, detail="없는 글타래입니다.")
    return thread


@router.get("/threads")
def list_threads(
    user: CurrentUser = Depends(require_spotter), db: Session = Depends(get_db)
) -> dict[str, Any]:
    """게시판 목록. **열린 것이 먼저다.**

    닫힌 글타래도 남긴다 — 「이건 왜 이렇게 결론이 났나」를 나중에 다시 묻는
    사람이 있고, 그때 답이 남아 있어야 같은 이야기를 두 번 안 한다.
    """
    ensure_threads(db)
    threads = db.scalars(select(SpotterThread).order_by(SpotterThread.updated_at.desc())).all()
    rows = db.scalars(select(SpotterReport)).all()
    counts = _comment_counts(db)
    out = [_thread_row(t, rows, counts.get(t.id, 0)) for t in threads]
    # 열린 것이 먼저, 그 안에서는 걸린 사람이 많은 것이 먼저. 수가 같으면
    # 위의 질의가 세운 순서(최근 이야기 순)가 그대로 남는다 — 파이썬의 정렬이
    # 자리를 안 바꾸기 때문이다.
    out.sort(key=lambda t: (t["status"] != SPOTTER_REPORT_OPEN, -t["reports"]))
    return {
        "threads": out,
        "open": sum(1 for t in out if t["status"] == SPOTTER_REPORT_OPEN),
        "min": SPOTTER_ALERT_MIN,
    }


@router.get("/threads/{kind}/{subject:path}")
def get_thread(
    kind: str,
    subject: str,
    user: CurrentUser = Depends(require_spotter),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """글타래 하나. 걸린 제보와 달린 의견을 함께 낸다."""
    thread = _find_thread(db, kind, subject)
    rows = db.scalars(select(SpotterReport)).all()
    mine = _thread_reports(thread, rows)

    comments = db.scalars(
        select(SpotterComment)
        .where(SpotterComment.thread_id == thread.id)
        .order_by(SpotterComment.created_at)
    ).all()
    names = _names(db, {row.user_id for row in mine} | {c.user_id for c in comments})

    data = _thread_row(thread, rows, sum(1 for c in comments if not c.deleted))
    data["notes"] = [
        {
            "kind": row.kind,
            "note": row.note,
            "who": names.get(row.user_id, "알 수 없음"),
            "at": _iso(row.created_at),
            "questionId": row.question_id,
        }
        for row in sorted(mine, key=lambda r: r.created_at)
    ]
    data["comments"] = [
        {
            "id": c.id,
            "who": names.get(c.user_id, "알 수 없음"),
            "body": "" if c.deleted else c.body,
            "deleted": c.deleted,
            "mine": c.user_id == user.id,
            "at": _iso(c.created_at),
        }
        for c in comments
    ]
    data["isAdmin"] = user.is_admin
    return data


class CommentIn(BaseModel):
    body: str = ""


@router.post("/threads/{kind}/{subject:path}/comments")
def add_comment(
    kind: str,
    subject: str,
    payload: CommentIn,
    user: CurrentUser = Depends(require_spotter),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    thread = _find_thread(db, kind, subject)
    body = payload.body.strip()[:SPOTTER_COMMENT_MAX]
    if not body:
        raise HTTPException(status_code=400, detail="내용을 적어 주세요.")
    db.add(SpotterComment(thread_id=thread.id, user_id=user.id, body=body))
    # 목록이 「최근 이야기」를 알려면 글타래도 같이 움직여야 한다.
    thread.updated_at = datetime.now(UTC)
    db.commit()
    return get_thread(kind, subject, user, db)


@router.delete("/comments/{comment_id}")
def delete_comment(
    comment_id: int,
    user: CurrentUser = Depends(require_spotter),
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    """내 글만 지운다(관리자는 아무 글이나).

    **줄은 남기고 내용만 비운다.** 오간 대화에서 한 줄이 통째로 사라지면
    남은 줄들이 무엇에 답한 것인지 알 수 없게 된다.
    """
    row = db.get(SpotterComment, comment_id)
    if row is None:
        raise HTTPException(status_code=404, detail="없는 글입니다.")
    if row.user_id != user.id and not user.is_admin:
        raise HTTPException(status_code=403, detail="내가 쓴 글만 지울 수 있습니다.")
    row.deleted = True
    row.body = ""
    db.commit()
    return {"deleted": True}


class ThreadPatch(BaseModel):
    status: str = ""
    verdict: str = ""


@router.patch("/admin/threads/{kind}/{subject:path}")
def update_thread(
    kind: str,
    subject: str,
    payload: ThreadPatch,
    user: CurrentUser = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """결론을 적고 닫는다.

    **닫는 것이 곧 다시 내보내는 것이다** — 열린 글타래의 문항은 새 세트에서
    빠지므로, 닫기 전에 문항을 고쳐서 다시 구워야 한다.
    """
    thread = _find_thread(db, kind, subject)
    if payload.status:
        if payload.status not in SPOTTER_REPORT_STATUSES:
            raise HTTPException(status_code=400, detail="상태 값이 올바르지 않습니다.")
        thread.status = payload.status
    thread.verdict = payload.verdict.strip()[:2000]
    db.commit()
    return get_thread(kind, subject, user, db)


@router.get("/flagged")
def list_flagged(
    user: CurrentUser = Depends(require_spotter), db: Session = Depends(get_db)
) -> dict[str, Any]:
    """점검 중이라 **새 세트에서 뺄 것들**.

    문항 DB에 표시를 심지 않는 까닭은, 그 DB가 R2에 올려 둔 한 덩어리여서
    문항 하나를 격리하는 데 5MB를 다시 굽고 다시 올려야 하기 때문이다. 목록만
    따로 내면 제보가 들어온 다음 판부터 바로 빠진다.

    사진은 이름으로 낸다. 어느 문항이 그 사진을 쓰는지는 화면이 이미 안다.
    """
    ensure_threads(db)
    threads = db.scalars(
        select(SpotterThread).where(SpotterThread.status == SPOTTER_REPORT_OPEN)
    ).all()
    return {
        "questions": [t.subject for t in threads if t.kind == SPOTTER_THREAD_QUESTION],
        "images": [t.subject for t in threads if t.kind == SPOTTER_THREAD_IMAGE],
        "min": SPOTTER_ALERT_MIN,
    }


@router.post("/admin/reports/{question_id}/close")
def close_question(
    question_id: str,
    user: CurrentUser = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, int]:
    """이 문항에 걸린 제보를 한꺼번에 닫는다.

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
