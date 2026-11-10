"""누가 이 사이트를 쓰고 있는가. **읽기만 한다.**

2026-09-19 관리자 지시 — 「사용자별 사이트 이용현황을 내가 볼 수 있게 하고 싶어.」
Study_EZ 몫만 센다(땡시는 여기 없다 — 같은 날 범위를 그렇게 정했다).

    GET /api/admin/usage?window=block   사람마다 한 줄
    GET /api/admin/usage/{user_id}      그 사람의 강의별 내역 (이쪽은 기간을 안 자른다)

## 기간을 자른다

**누적은 질문에 답을 못 한다.** 한 번 찬 수는 안 줄어서, 두 달 전에 열심히 한
사람과 이번 주에 하는 사람이 같은 크기로 보인다. 그래서 요약의 수는 전부 **창
안에서만** 센다(2026-09-19 관리자 지시 — 「너무 오래된 것까지 영향을 주지 않게」).

    block   이번 블럭    지금 도는 블럭이 시작한 날부터 지금까지   ← 기본값
    prev    지난 블럭    그 앞 블럭의 시작부터 이번 블럭 시작까지
    week    최근 7일     복습의 하루 경계로 이레

**블럭은 표에서 읽는다**(`_blocks`). 이 저장소에서 블럭은 과목이고(`bundles.py`
첫 줄), 그 시작과 끝은 `lecture.date` 의 최소·최대다. 따로 적어 두는 자리를
만들지 않은 것은 그러면 강의가 늘 때마다 두 곳을 고쳐야 하기 때문이다.

**무엇을 쟀는지 같이 내보낸다**(`window.label`·`from`·`to`). 화면이 「이번 블럭」
이라고만 적으면 보는 사람이 그게 언제부터인지 모른다.

`lastAt` 만 창을 안 탄다. 「마지막으로 무엇이든 한 때」는 창을 자르면 뜻이 없다.

## 셀 수 있는 것과 없는 것

**apkg 로 나간 풀이는 서버에 없다.** 덱은 안키에서 풀리고 그 진행은 안키가 든다.
그래서 여기 숫자는 *웹 평가·대화 저장·링크 클릭·파일 요청*이며, 이를 더해
「이 사람이 얼마나 공부했나」로 읽으면 안 된다.

`AssetGrab`은 파일 요청이다. 자동 첨부·브라우저 열기·직접 받기를 purpose로 구분하고,
과거 미분류는 unknown으로 유지한다. 요청은 전송/첨부 완료를 증명하지 않는다.

**기본 링크를 누가 열었는지는 링크로는 알 수 없다.** 강의당 하나이고
(`preview.share_url`) 누르면 그 길로 AI 쪽으로 가서 서버를 안 지난다. 세는 것은
**우리 화면에서 누른 것**뿐이라(`PreviewOpen`), 링크를 복사해 받은 사람이 연 것은
안 들어온다. **2026-09-19 부터만 있다** — 그 전은 0으로 보이므로 그 0을 가르라고
`opensSince`(그 표의 가장 오래된 줄)를 같이 낸다.

**접속 기록은 두지 않는다.** 표를 하나 세웠다가 같은 날 걷어냈다(관리자 지시 —
「접속기록표는 없애자. 어차피 마지막 접속으로 알 수 있다」). `lastAt` 이 그 답을
이미 하고, 표 하나를 덜 이고 간다.

`correct` 는 **본인이 찍은 것**이다(`_Attempt`). 자유회상 카드라 서버가 판정한
값이 아니므로 `selfCorrect` 로 낸다. 정답률로 그리면 안 되는 값이다.

## 0을 가른다

활동이 0인 줄은 두 가지다 — **안 쓴 사람**과 **아직 승인이 안 나 못 쓰는 사람.**
화면에는 같은 0으로 보인다. 그래서 `hasAccess`(`app_grant(studyez)`)를 같이 낸다.
루트 `CLAUDE.md` 의 함정 ③ 이 이것이다.
"""

from __future__ import annotations
from app.models.connections import ConnectionEvent
from app.models.lecture_notes import LectureMemo, NoteRead
from app.models.root_learning import RootEvent

from datetime import UTC, datetime, time, timedelta
from datetime import date as Date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, func, select, union
from sqlalchemy.orm import Session

from app import srs
from app.study_retention import event_identity
from app.auth import CurrentUser, require_admin
from app.database import get_db
from app.file_requests import FILE_PURPOSES, request_stats
from app.usage_actions import ACTION_GROUPS, catalog, collect
from app.models import (
    APP_STUDYEZ,
    PREVIEW_OPEN_KINDS,
    AppGrant,
    AssetGrab,
    BankFeedback,
    BankState,
    BankStateArchive,
    Lecture,
    MainAttempt,
    MainReviewLog,
    PreReviewLog,
    PreviewOpen,
    Profile,
    QuizAttempt,
    UserPreview,
)

router = APIRouter()

ROOT_FIELDS = ('rootStarts', 'rootAttempts', 'rootRatings', 'rootUndos', 'rootTiers', 'rootGenerations', 'rootGenerated')

def _root_field(event):
    if event.kind == 'reveal' and event.payload.get('attempted'):
        return 'rootAttempts'
    return {'start':'rootStarts', 'rate':'rootRatings', 'undo':'rootUndos', 'tier':'rootTiers',
            'generation':'rootGenerations', 'generated':'rootGenerated'}.get(event.kind)


#: 「최근」 창의 크기. 블럭이 아직 없을 때의 기본이기도 하다.
WEEK_DAYS = 7

#: 화면이 고를 수 있는 창. 순서가 화면의 버튼 순서다.
WINDOW_KEYS = ("block", "prev", "week")


def _as_utc(when: datetime | None) -> datetime | None:
    """SQLite 는 시간대를 안 싣고 돌려준다. 내보내기 전에 여기서 붙인다."""
    if when is None:
        return None
    return when if when.tzinfo else when.replace(tzinfo=UTC)


def _iso(when: datetime | None) -> str | None:
    marked = _as_utc(when)
    return marked.isoformat() if marked else None


def _parse(iso: str | None) -> datetime | None:
    """`lastAt` 을 문자열로 들고 있으므로 견줄 때 되돌린다."""
    return datetime.fromisoformat(iso) if iso else None


def _latest(*times: datetime | None) -> datetime | None:
    found = [marked for marked in (_as_utc(when) for when in times) if marked]
    return max(found) if found else None


def _kst_midnight(day: Date) -> datetime:
    """그 날이 한국에서 시작하는 시각. 표의 시각은 전부 UTC 라 여기서 옮긴다."""
    return datetime.combine(day, time(), tzinfo=UTC) - srs.KST_OFFSET


def _blocks(db: Session) -> list[tuple[str, Date, Date]]:
    """블럭을 끝난 순으로. **블럭은 과목이고 그 범위는 강의 날짜다.**

    따로 적어 두는 자리를 안 만든 이유는 모듈 첫머리에 있다 — 강의가 늘 때마다
    두 곳을 고쳐야 하는 값은 한쪽만 고쳐진다.
    """
    rows = db.execute(
        select(Lecture.subject, func.min(Lecture.date), func.max(Lecture.date)).group_by(
            Lecture.subject
        )
    ).all()
    return sorted(((subject, start, end) for subject, start, end in rows), key=lambda row: row[2])


def _window(db: Session, key: str, now: datetime) -> dict[str, Any]:
    """무엇을 재는 창인가. `from`·`to` 는 UTC 시각이고 `to` 가 `None` 이면 지금까지다.

    **블럭이 없으면 이레로 내려앉는다.** 학기 첫날처럼 강의가 한 편도 없는 날에
    빈 화면을 주지 않기 위해서다 — 그때는 `key` 가 `week` 로 바뀌어 돌아가므로
    화면이 고른 것과 잰 것이 어긋나지 않는다.
    """
    week = {
        "key": "week",
        "label": f"최근 {WEEK_DAYS}일",
        "from": srs.day_start(now) - timedelta(days=WEEK_DAYS - 1),
        "to": None,
    }
    if key == "week":
        return week

    blocks = _blocks(db)
    today = srs.day_key(now)
    # 이번 블럭 = 이미 시작한 것 중 가장 늦게 끝나는 것. 학기 끝에 서 있으면
    # 마지막 블럭이 그대로 「이번」이다 — 그 편을 아직 보는 사람이 있다.
    started = [block for block in blocks if block[1] <= today]
    if not started:
        return week
    current = started[-1]
    if key == "prev":
        if len(started) < 2:
            return week
        previous = started[-2]
        return {
            "key": "prev",
            "label": f"지난 블럭 · {previous[0]}",
            "from": _kst_midnight(previous[1]),
            "to": _kst_midnight(current[1]),
        }
    return {
        "key": "block",
        "label": f"이번 블럭 · {current[0]}",
        "from": _kst_midnight(current[1]),
        "to": None,
    }


def _within(stamp: Any, window: dict[str, Any]) -> list[Any]:
    """창으로 자르는 조건. `to` 가 없으면 지금까지라 조건이 하나다."""
    bounds = [stamp >= window["from"]]
    if window["to"] is not None:
        bounds.append(stamp < window["to"])
    return bounds


def _count_by_user(db: Session, model: Any, stamp: Any, window: dict[str, Any]) -> dict[str, int]:
    """창 안의 줄 수를 사람마다. 카드 한 장이 한 줄이다(`_Attempt`)."""
    rows = db.execute(
        select(model.user_id, func.count()).where(*_within(stamp, window)).group_by(model.user_id)
    ).all()
    return {user_id: int(count) for user_id, count in rows}


def _lecture_counts(db: Session, *sources: Any) -> dict[str, int]:
    """사람마다 편 수. 표가 여럿이면 `union` 이 겹치는 편을 지운다."""
    inner = union(*sources).subquery() if len(sources) > 1 else sources[0].distinct().subquery()
    rows = db.execute(select(inner.c.user_id, func.count()).group_by(inner.c.user_id)).all()
    return {user_id: int(count) for user_id, count in rows}


def _file_activity(db: Session, user_id: str | None = None):
    query = select(AssetGrab)
    if user_id is not None:
        query = query.where(AssetGrab.user_id == user_id)
    for grab in db.scalars(query):
        for purpose, stats in request_stats(grab).items():
            yield grab, purpose, stats


def _bank_activity(db: Session, user_id: str | None = None):
    """Read review history without downloading the other state/session fields.

    An ungraded reveal is not a review. Undo removes the review from history.
    Include the previous build kept by BankState, even when its bank is hidden.
    """
    query = select(
        BankState.user_id, BankState.subject, BankState.run_id, BankState.build_id,
        BankState.state["history"], BankState.previous["build_id"].as_string(),
        BankState.previous["state"]["history"], BankState.state['review_tombstones'],
        BankState.previous['state']['review_tombstones'],
    )
    ranked = select(BankStateArchive.id, func.row_number().over(
        partition_by=(BankStateArchive.user_id, BankStateArchive.subject, BankStateArchive.run_id, BankStateArchive.build_id),
        order_by=(BankStateArchive.created_at.desc(), BankStateArchive.id.desc())).label('position'))
    if user_id is not None:
        ranked = ranked.where(BankStateArchive.user_id == user_id)
    ranked = ranked.subquery()
    archives = select(BankStateArchive.user_id, BankStateArchive.subject, BankStateArchive.run_id,
                      BankStateArchive.build_id, BankStateArchive.state['history'],
                      BankStateArchive.state['review_tombstones']).join(ranked, ranked.c.id == BankStateArchive.id).where(
                          ranked.c.position == 1)
    if user_id is not None:
        query = query.where(BankState.user_id == user_id)
        archives = archives.where(BankStateArchive.user_id == user_id)
    snapshots = {}
    tombstones = {}
    for uid, subject, run_id, build, history, undone in db.execute(archives):
        snapshots.setdefault((uid, subject, run_id), {})[build] = history or []
        tombstones.setdefault((uid, subject, run_id), set()).update(undone or [])
    for uid, subject, run_id, build, history, old_build, old_history, undone, old_undone in db.execute(query):
        versions = snapshots.setdefault((uid, subject, run_id), {})
        tombstones.setdefault((uid, subject, run_id), set()).update([*(undone or []), *(old_undone or [])])
        if old_build:
            versions[old_build] = old_history or []
        versions[build] = history or []
    for (uid, subject, run_id), versions in snapshots.items():
        reviews = {}
        for build_id, entries in versions.items():
            for entry in entries or []:
                if event_identity(build_id, entry) in tombstones[(uid, subject, run_id)]:
                    continue
                qid, stamp, rating = entry.get("question_id"), entry.get("timestamp"), entry.get("rating")
                if not qid or not isinstance(stamp, (int, float)) or rating not in ("Again", "Hard", "Good", "Easy"):
                    continue
                key = (entry.get('origin_build_id', build_id), entry.get('origin_question_id', qid), stamp)
                reviews[key] = rating
        yield uid, subject, run_id, reviews


@router.get("/usage")
def usage(
    window: str = Query("block"),
    user: CurrentUser = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """사람마다 한 줄. **가입한 사람 전부가 온다** — 안 쓴 줄도 답이다.

    수는 **창 안에서만** 센다(모듈 첫머리). 정렬만 창을 안 탄다 — 마지막 활동
    최신순이라 창을 바꿔도 줄 순서가 안 흔들리고, 그래야 같은 사람을 창마다
    견줄 수 있다.
    """
    now = datetime.now(UTC)
    if window not in WINDOW_KEYS:
        raise HTTPException(status_code=422, detail=f"없는 기간입니다: {window}")
    span = _window(db, window, now)

    granted = set(db.scalars(select(AppGrant.user_id).where(AppGrant.app == APP_STUDYEZ)).all())
    # 푼 카드. **한 줄이 한 장이다** — 같은 카드를 세 번 봐도 줄은 하나고,
    # `answered_at` 은 마지막으로 찍은 때라 그 장이 창 안에 있었는지를 말한다.
    pre_cards = _count_by_user(db, QuizAttempt, QuizAttempt.answered_at, span)
    connection_saves = _count_by_user(db, ConnectionEvent, ConnectionEvent.created_at, span)
    question_reports = _count_by_user(db, BankFeedback, BankFeedback.created_at, span)
    # 강의록 회독: 지운 회독은 줄이 없어 세지 않는다. 메모: 창 안에 마지막으로 고친 강의 수.
    note_reads = _count_by_user(db, NoteRead, NoteRead.created_at, span)
    memos = _count_by_user(db, LectureMemo, LectureMemo.updated_at, span)
    root_metrics = {}
    for event in db.scalars(select(RootEvent).where(*_within(RootEvent.created_at, span))):
        field = _root_field(event)
        if field:
            metrics = root_metrics.setdefault(event.user_id, {})
            metrics[field] = metrics.get(field, 0) + 1
    main_cards = _count_by_user(db, MainAttempt, MainAttempt.answered_at, span)
    preview_saves = {
        uid: int(count) for uid, count in db.execute(
            select(UserPreview.user_id, func.count()).where(
                UserPreview.conversation_url != "", *_within(UserPreview.updated_at, span)
            ).group_by(UserPreview.user_id)
        )
    }
    file_lectures: dict[tuple[str, str], set[tuple[str, str]]] = {}
    for grab, purpose, stats in _file_activity(db):
        at = _parse(stats["lastAt"])
        if at >= span["from"] and (span["to"] is None or at < span["to"]):
            file_lectures.setdefault((grab.user_id, purpose), set()).add((grab.subject, grab.run_id))
    bank_cards: dict[str, int] = {}
    bank_last: dict[str, datetime] = {}
    for uid, _, _, reviews in _bank_activity(db):
        cards = set()
        for (build, qid, stamp), _rating in reviews.items():
            at = datetime.fromtimestamp(stamp / 1000, UTC)
            bank_last[uid] = _latest(bank_last.get(uid), at)
            if at >= span["from"] and (span["to"] is None or at < span["to"]):
                cards.add((build, qid))
        bank_cards[uid] = bank_cards.get(uid, 0) + len(cards)
    # 받은 덱·연 링크는 **편으로 센다.** 횟수는 「다시 받으러 왔다」를 말할 뿐이고,
    # 관리자가 묻는 것은 「몇 편을 챙겼나」다.
    grab_lectures = _lecture_counts(
        db,
        select(AssetGrab.user_id, AssetGrab.subject, AssetGrab.run_id).where(
            *_within(AssetGrab.last_at, span)
        ),
    )
    opens: dict[str, dict[str, int]] = {}
    creates: dict[str, int] = {}
    for uid, kind, lectures in db.execute(
        select(PreviewOpen.user_id, PreviewOpen.kind, func.count())
        .where(*_within(PreviewOpen.last_at, span))
        .group_by(PreviewOpen.user_id, PreviewOpen.kind)
    ).all():
        if kind == "create":
            creates[uid] = int(lectures)
        elif kind in PREVIEW_OPEN_KINDS:
            opens.setdefault(uid, dict.fromkeys(PREVIEW_OPEN_KINDS, 0))[kind] = int(lectures)

    # ── 여기부터는 창을 안 탄다. 「마지막으로 무엇이든 한 때」와 사람의 설정이다.
    last_seen: dict[str, datetime | None] = dict(bank_last)
    for model, stamp in (
        (QuizAttempt, QuizAttempt.answered_at),
        (MainAttempt, MainAttempt.answered_at),
        (PreReviewLog, PreReviewLog.reviewed_at),
        (MainReviewLog, MainReviewLog.reviewed_at),
        (AssetGrab, AssetGrab.last_at),
        (PreviewOpen, PreviewOpen.last_at),
        (UserPreview, UserPreview.updated_at),
        (ConnectionEvent, ConnectionEvent.created_at),
        (RootEvent, RootEvent.created_at),
        (BankFeedback, BankFeedback.created_at),
        (NoteRead, NoteRead.created_at),
        (LectureMemo, LectureMemo.updated_at),
    ):
        for uid, last in db.execute(
            select(model.user_id, func.max(stamp)).group_by(model.user_id)
        ).all():
            last_seen[uid] = _latest(last, last_seen.get(uid))
    # **개인 대화만 센다.** 빈 줄은 저장했다 지운 자리라 「만든 적 있다」가 아니다.
    previews = {
        uid: int(count)
        for uid, count in db.execute(
            select(UserPreview.user_id, func.count())
            .where(UserPreview.conversation_url != "")
            .group_by(UserPreview.user_id)
        ).all()
    }

    rows: list[dict[str, Any]] = []
    for profile in db.scalars(select(Profile)).all():
        uid = profile.id
        rows.append(
            {
                "id": uid,
                "connectionSaves": connection_saves.get(uid, 0),
                "questionReports": question_reports.get(uid, 0),
                "noteReads": note_reads.get(uid, 0),
                "memos": memos.get(uid, 0),
                **{field: root_metrics.get(uid, {}).get(field, 0) for field in ROOT_FIELDS},
                "email": profile.email,
                "isAdmin": profile.is_admin,
                # 0이 「안 썼다」인지 「못 썼다」인지를 가르는 값이다. 위를 보라.
                "hasAccess": uid in granted,
                "joinedAt": _iso(profile.created_at),
                "lastAt": _iso(last_seen.get(uid)),
                # ── 창 안의 값 셋. 화면의 칸과 하나씩 짝이다.
                "cards": pre_cards.get(uid, 0) + main_cards.get(uid, 0) + bank_cards.get(uid, 0),
                "quizzes": {"pre": pre_cards.get(uid, 0), "main": main_cards.get(uid, 0),
                            "bank": bank_cards.get(uid, 0)},
                "previewSaves": preview_saves.get(uid, 0),
                "previewCreates": creates.get(uid, 0),
                "fileRequests": {purpose: len(file_lectures.get((uid, purpose), set()))
                                 for purpose in FILE_PURPOSES},
                "decks": grab_lectures.get(uid, 0),
                "opens": opens.get(uid, dict.fromkeys(PREVIEW_OPEN_KINDS, 0)),
                # ── 창을 안 타는 것. 펴서 보는 자리에 쓴다.
                "previews": previews.get(uid, 0),
                "prompt": {
                    "custom": bool(profile.preview_prompt.strip()),
                    "chars": len(profile.preview_prompt.strip()),
                },
            }
        )

    for row in rows:
        row["activities"] = collect(row)

    # 쓰는 사람이 위, 한 번도 안 연 사람이 아래. 안 연 사람끼리는 가입 순이라
    # **승인하고 안 들어온 사람이 맨 밑에 모인다.**
    active = sorted(
        (row for row in rows if row["lastAt"]), key=lambda row: row["lastAt"], reverse=True
    )
    idle = sorted((row for row in rows if not row["lastAt"]), key=lambda row: row["joinedAt"] or "")

    return {
        "now": now.isoformat(),
        "window": {
            # 고른 것이 아니라 **실제로 잰 것**이다. 블럭이 없으면 여기가 week 로 온다.
            "key": span["key"],
            "label": span["label"],
            "from": _iso(span["from"]),
            "to": _iso(span["to"]),
        },
        "windows": [{"key": key, "label": _window(db, key, now)["label"]} for key in WINDOW_KEYS],
        # **언제부터 남았는가.** 이 값이 없으면 화면이 0을 「안 했다」로 그린다.
        "opensSince": _iso(db.scalar(select(func.min(PreviewOpen.first_at)).where(PreviewOpen.kind.in_(PREVIEW_OPEN_KINDS)))),
        "users": active + idle,
        "activityCatalog": catalog(),
        "activityGroups": ACTION_GROUPS,
    }


@router.get("/usage/{user_id}")
def usage_detail(
    user_id: str,
    user: CurrentUser = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """한 사람이 강의마다 무엇을 했는가. 최근에 손댄 편이 먼저다.

    **강의가 지워져도 줄은 남는다.** `asset_grab` 에는 `lecture` 로 가는 외래키가
    없어서(표 정의를 보라) 편이 사라진 뒤에도 받아 간 기록이 남는다. 그런 줄의
    제목은 비어 있고, 화면은 `run_id` 로 그린다 — 조용히 버리면 받아 간 수가
    요약과 안 맞는다.
    """
    profile = db.get(Profile, user_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="계정을 찾을 수 없습니다.")

    def empty() -> dict[str, Any]:
        return {
            "pre": {"cards": 0, "selfCorrect": 0, "grades": 0},
            "main": {"cards": 0, "selfCorrect": 0, "grades": 0},
            "bank": {"cards": 0, "selfCorrect": 0, "grades": 0},
            "grabs": [],
            "fileRequests": [],
            "preview": False,
            "previewSavedAt": None,
            "connectionSaves": {"count": 0, "lastAt": None},
            "questionReports": {"count": 0, "lastAt": None},
            "noteReads": {"count": 0, "lastAt": None},
            "memo": {"count": 0, "lastAt": None},
            **{field: {"count":0,"lastAt":None} for field in ROOT_FIELDS},
            "previewCreates": {"count": 0, "lastAt": None},
            "quizLastAt": {"pre": None, "main": None, "bank": None},
            # 우리 화면에서 이 편의 링크를 누른 횟수. 갈래로 갈라 둔다.
            "opens": dict.fromkeys(PREVIEW_OPEN_KINDS, 0),
            "opensAt": dict.fromkeys(PREVIEW_OPEN_KINDS, None),
            "lastAt": None,
        }

    lectures: dict[tuple[str, str], dict[str, Any]] = {}

    def slot(subject: str, run_id: str) -> dict[str, Any]:
        return lectures.setdefault((subject, run_id), empty())

    for _, subject, run_id, reviews in _bank_activity(db, user_id):
        if not reviews:
            continue
        row = slot(subject, run_id)
        latest = {}
        for (build, qid, stamp), rating in sorted(reviews.items(), key=lambda pair: pair[0][2]):
            latest[(build, qid)] = rating
        row["bank"] = {"cards": len(latest), "selfCorrect": sum(r in ("Good", "Easy") for r in latest.values()),
                       "grades": len(reviews)}
        last = datetime.fromtimestamp(max(key[2] for key in reviews) / 1000, UTC)
        row["lastAt"] = _iso(_latest(last, _parse(row["lastAt"])))
        row["quizLastAt"]["bank"] = _iso(last)

    for subject, run_id, count, last in db.execute(select(
        ConnectionEvent.subject, ConnectionEvent.run_id, func.count(), func.max(ConnectionEvent.created_at)
    ).where(ConnectionEvent.user_id == user_id).group_by(ConnectionEvent.subject, ConnectionEvent.run_id)):
        row = slot(subject, run_id)
        row['connectionSaves'] = {'count': count, 'lastAt': _iso(last)}
        row['lastAt'] = _iso(_latest(last, _parse(row['lastAt'])))

    for subject, run_id, count, last in db.execute(select(
        NoteRead.subject, NoteRead.run_id, func.count(), func.max(NoteRead.created_at)
    ).where(NoteRead.user_id == user_id).group_by(NoteRead.subject, NoteRead.run_id)):
        row = slot(subject, run_id)
        row['noteReads'] = {'count': count, 'lastAt': _iso(last)}
        row['lastAt'] = _iso(_latest(last, _parse(row['lastAt'])))

    for memo in db.scalars(select(LectureMemo).where(LectureMemo.user_id == user_id)):
        row = slot(memo.subject, memo.run_id)
        row['memo'] = {'count': 1, 'lastAt': _iso(memo.updated_at)}
        row['lastAt'] = _iso(_latest(memo.updated_at, _parse(row['lastAt'])))

    for subject, run_id, count, last in db.execute(select(
        BankFeedback.subject, BankFeedback.run_id, func.count(), func.max(BankFeedback.created_at)
    ).where(BankFeedback.user_id == user_id).group_by(BankFeedback.subject, BankFeedback.run_id)):
        row = slot(subject, run_id)
        row['questionReports'] = {'count': count, 'lastAt': _iso(last)}
        row['lastAt'] = _iso(_latest(last, _parse(row['lastAt'])))

    for event in db.scalars(select(RootEvent).where(RootEvent.user_id == user_id)):
        field = _root_field(event)
        if field:
            row = slot(event.subject, event.run_id)
            row[field]['count'] += 1
            row[field]['lastAt'] = _iso(_latest(event.created_at, _parse(row[field]['lastAt'])))
            row['lastAt'] = _iso(_latest(event.created_at, _parse(row['lastAt'])))

    for track, model in (("pre", QuizAttempt), ("main", MainAttempt)):
        rows = db.execute(
            select(
                model.subject,
                model.run_id,
                func.count(),
                # **`cast(bool AS int)` 을 쓰지 않는다.** SQLite 는 받지만 표준이
                # 아니고, 옮겨 갈 DB 마다 되는지 다시 재야 한다. `case` 는 어디서나 같다.
                func.sum(case((model.correct, 1), else_=0)),
                func.max(model.answered_at),
            )
            .where(model.user_id == user_id)
            .group_by(model.subject, model.run_id)
        ).all()
        for subject, run_id, cards, correct, last in rows:
            row = slot(subject, run_id)
            # 서버가 판정한 값이 아니다. 이름이 그렇게 말한다.
            row[track].update(cards=int(cards), selfCorrect=int(correct or 0))
            row["quizLastAt"][track] = _iso(last)
            row["lastAt"] = _iso(_latest(last, _parse(row["lastAt"])))

    for track, model, stamp in (
        ("pre", PreReviewLog, PreReviewLog.reviewed_at),
        ("main", MainReviewLog, MainReviewLog.reviewed_at),
    ):
        rows = db.execute(
            select(model.subject, model.run_id, func.count(), func.max(stamp))
            .where(model.user_id == user_id)
            .group_by(model.subject, model.run_id)
        ).all()
        for subject, run_id, grades, last in rows:
            row = slot(subject, run_id)
            row[track]["grades"] = int(grades)
            row["quizLastAt"][track] = _iso(_latest(last, _parse(row["quizLastAt"][track])))
            row["lastAt"] = _iso(_latest(last, _parse(row["lastAt"])))

    for grab, purpose, stats in _file_activity(db, user_id):
        row = slot(grab.subject, grab.run_id)
        if grab.kind not in row["grabs"]:
            row["grabs"].append(grab.kind)
        row["fileRequests"].append({"kind": grab.kind, "purpose": purpose, **stats})
        row["lastAt"] = _iso(_latest(_parse(stats["lastAt"]), _parse(row["lastAt"])))

    for subject, run_id, kind, times, last in db.execute(
        select(
            PreviewOpen.subject, PreviewOpen.run_id, PreviewOpen.kind, PreviewOpen.count, PreviewOpen.last_at
        ).where(PreviewOpen.user_id == user_id)
    ).all():
        row = slot(subject, run_id)
        if kind == "create":
            row["previewCreates"] = {"count": int(times or 0), "lastAt": _iso(last)}
        elif kind in PREVIEW_OPEN_KINDS:
            row["opens"][kind] = int(times or 0)
            row["opensAt"][kind] = _iso(last)
        row["lastAt"] = _iso(_latest(last, _parse(row["lastAt"])))

    for subject, run_id, last in db.execute(
        select(UserPreview.subject, UserPreview.run_id, UserPreview.updated_at).where(
            UserPreview.user_id == user_id, UserPreview.conversation_url != ""
        )
    ).all():
        row = slot(subject, run_id)
        row["preview"] = True
        row["previewSavedAt"] = _iso(last)
        row["lastAt"] = _iso(_latest(last, _parse(row["lastAt"])))

    titles = {
        (lecture.subject, lecture.run_id): lecture
        for lecture in db.scalars(select(Lecture)).all()
    }
    out = []
    for (subject, run_id), row in lectures.items():
        lecture = titles.get((subject, run_id))
        row["grabs"].sort()
        row["fileRequests"].sort(key=lambda item: (item["lastAt"], item["kind"], item["purpose"]), reverse=True)
        row["activities"] = collect(row, detail=True)
        out.append(
            {
                "subject": subject,
                "runId": run_id,
                # 지워진 편은 제목이 없다. 화면이 `run_id` 로 그린다 — 위를 보라.
                "title": lecture.title if lecture else "",
                "date": lecture.date.isoformat() if lecture else None,
                **row,
            }
        )
    out.sort(key=lambda row: (row["lastAt"] or "", row["runId"]), reverse=True)

    return {
        "user": {
            "id": profile.id,
            "email": profile.email,
            # 고쳐 쓴 사람만 값이 있다. 빈 문자열은 「기본 문구를 쓴다」는 뜻이다.
            "previewPrompt": profile.preview_prompt.strip(),
        },
        "now": datetime.now(UTC).isoformat(),
        "lectures": out,
        "activityCatalog": catalog(),
        "activityGroups": ACTION_GROUPS,
    }
