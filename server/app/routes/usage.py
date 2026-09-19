"""누가 이 사이트를 쓰고 있는가. **읽기만 한다.**

2026-09-19 관리자 지시 — 「사용자별 사이트 이용현황을 내가 볼 수 있게 하고 싶어.」
Study_EZ 몫만 센다(땡시는 여기 없다 — 같은 날 범위를 그렇게 정했다).

    GET /api/admin/usage             사람마다 한 줄
    GET /api/admin/usage/{user_id}   그 사람의 강의별 내역

## 셀 수 있는 것과 없는 것

**apkg 로 나간 풀이는 서버에 없다.** 덱은 안키에서 풀리고 그 진행은 안키가 든다.
그래서 여기 숫자는 전부 *웹에서 한 것*과 *파일을 받아 간 것*이고, 둘을 더해
「이 사람이 얼마나 공부했나」로 읽으면 안 된다. 화면도 그렇게 안 그린다.

같은 이유로 **받아 간 것은 「받아 갔다」지 「풀었다」가 아니다**(`AssetGrab` 의
설명이 그 자리다). `count` 는 서명 URL 이 TTL 동안 재사용되므로 내려받은 횟수가
아니라 **버튼을 누른 횟수**에 가깝다 — 이름도 `clicks` 로 낸다.

**접속과 링크 열기는 2026-09-19 부터만 있다.** 그날 관리자 지시로 표 둘이
섰고(`user_visit`·`preview_open`), 그 전에 들어온 것은 아무 데도 안 남아 있다.
**그래서 0 을 「안 들어왔다」로 읽으면 안 된다** — 화면이 가를 수 있게 두 표의
가장 오래된 줄을 `visitsSince`·`opensSince` 로 같이 내보낸다.

**기본 링크를 누가 열었는지는 링크로는 알 수 없다.** 강의당 하나이고
(`preview.share_url`) 누르면 그 길로 AI 쪽으로 가서 서버를 안 지난다. 세는 것은
**우리 화면에서 누른 것**뿐이라(`PreviewOpen`), 링크를 복사해 받은 사람이 연 것은
안 들어온다.

`correct` 는 **본인이 찍은 것**이다(`_Attempt`). 자유회상 카드라 서버가 판정한
값이 아니므로 `selfCorrect` 로 낸다. 정답률로 그리면 안 되는 값이다.

## 0을 가른다

활동이 0인 줄은 두 가지다 — **안 쓴 사람**과 **아직 승인이 안 나 못 쓰는 사람.**
화면에는 같은 0으로 보인다. 그래서 `hasAccess`(`app_grant(studyez)`)를 같이 낸다.
루트 `CLAUDE.md` 의 함정 ③ 이 이것이다.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import case, func, select, union
from sqlalchemy.orm import Session

from app import srs
from app.auth import CurrentUser, require_admin
from app.database import get_db
from app.models import (
    APP_STUDYEZ,
    PREVIEW_OPEN_KINDS,
    AppGrant,
    AssetGrab,
    Lecture,
    MainAttempt,
    MainReviewLog,
    PreReviewLog,
    PreviewOpen,
    Profile,
    QuizAttempt,
    UserPreview,
    UserVisit,
)

router = APIRouter()

#: 「지금 쓰고 있나」를 보는 창. 누적 수는 한 번 차면 안 줄어서 그 답을 못 준다.
RECENT_DAYS = 7


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


def _by_user(db: Session, model: Any, stamp: Any, since: datetime | None = None) -> dict[str, tuple[int, datetime | None]]:
    """사람마다 (줄 수, 마지막 시각). 표 하나를 한 질의로 쓸어 담는다."""
    stmt = select(model.user_id, func.count(), func.max(stamp)).group_by(model.user_id)
    if since is not None:
        stmt = stmt.where(stamp >= since)
    return {user_id: (int(count), last) for user_id, count, last in db.execute(stmt).all()}


#: 편 하나를 가리키는 세 칸. 표가 달라도 이름이 같아서 `union` 이 그대로 붙는다.
PRE_KEYS = select(QuizAttempt.user_id, QuizAttempt.subject, QuizAttempt.run_id)
MAIN_KEYS = select(MainAttempt.user_id, MainAttempt.subject, MainAttempt.run_id)
GRAB_KEYS = select(AssetGrab.user_id, AssetGrab.subject, AssetGrab.run_id)


def _lecture_counts(db: Session, *sources: Any) -> dict[str, int]:
    """사람마다 편 수. 표가 여럿이면 `union` 이 겹치는 편을 지운다.

    **웹으로 푼 편과 받아 간 편을 따로도, 합쳐서도 센다.** 따로 세야 「웹에서
    푸는 사람인가 받아 가는 사람인가」가 보이고, 합쳐 세야 「한 편도 안 썼다」가
    거짓이 되지 않는다. 한쪽만 두면 둘 중 하나를 못 묻는다.
    """
    inner = (
        union(*sources).subquery() if len(sources) > 1 else sources[0].distinct().subquery()
    )
    rows = db.execute(select(inner.c.user_id, func.count()).group_by(inner.c.user_id)).all()
    return {user_id: int(count) for user_id, count in rows}


@router.get("/usage")
def usage(
    user: CurrentUser = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """사람마다 한 줄. **가입한 사람 전부가 온다** — 안 쓴 줄도 답이다.

    정렬은 마지막 활동 최신순이고, 활동이 없는 사람은 뒤에 가입순으로 선다.
    맨 위가 지금 쓰는 사람, 맨 아래가 한 번도 안 연 사람이다.
    """
    now = datetime.now(UTC)
    # 하루의 경계는 복습이 쓰는 그것이다(한국 시각 새벽 4시). 여기만 자정으로
    # 재면 「오늘 푼 것」이 두 화면에서 다른 수가 된다.
    since = srs.day_start(now) - timedelta(days=RECENT_DAYS - 1)

    granted = set(
        db.scalars(select(AppGrant.user_id).where(AppGrant.app == APP_STUDYEZ)).all()
    )
    pre_cards = _by_user(db, QuizAttempt, QuizAttempt.answered_at)
    main_cards = _by_user(db, MainAttempt, MainAttempt.answered_at)
    pre_grades = _by_user(db, PreReviewLog, PreReviewLog.reviewed_at)
    main_grades = _by_user(db, MainReviewLog, MainReviewLog.reviewed_at)
    pre_recent = _by_user(db, PreReviewLog, PreReviewLog.reviewed_at, since)
    main_recent = _by_user(db, MainReviewLog, MainReviewLog.reviewed_at, since)
    # **개인 대화만 센다.** 빈 줄은 저장했다 지운 자리라 「만든 적 있다」가 아니다.
    previews = db.execute(
        select(UserPreview.user_id, func.count(), func.max(UserPreview.updated_at))
        .where(UserPreview.conversation_url != "")
        .group_by(UserPreview.user_id)
    ).all()
    previews = {uid: (int(count), last) for uid, count, last in previews}
    grab_rows = db.execute(
        select(
            AssetGrab.user_id,
            func.count(),
            func.sum(AssetGrab.count),
            func.max(AssetGrab.last_at),
        ).group_by(AssetGrab.user_id)
    ).all()
    grabs = {row[0]: (int(row[1]), int(row[2] or 0), row[3]) for row in grab_rows}
    # **찍은 횟수가 아니라 카드 수다**(2026-09-19 관리자 지시 — 「차라리 카드 수」).
    # 같은 카드를 세 번 봐도 한 장이라, 「이 사람이 이 주에 무엇을 봤나」에 답한다.
    recent_cards = _lecture_counts(
        db,
        select(PreReviewLog.user_id, PreReviewLog.subject, PreReviewLog.run_id, PreReviewLog.item_id)
        .where(PreReviewLog.reviewed_at >= since),
        select(MainReviewLog.user_id, MainReviewLog.subject, MainReviewLog.run_id, MainReviewLog.item_id)
        .where(MainReviewLog.reviewed_at >= since),
    )
    visits = db.execute(
        select(
            UserVisit.user_id,
            func.count(),  # 들어온 날 수
            func.sum(UserVisit.count),  # 다시 온 횟수까지
            func.max(UserVisit.last_at),
        ).group_by(UserVisit.user_id)
    ).all()
    visits = {uid: (int(days), int(times or 0), last) for uid, days, times, last in visits}
    recent_days = {
        uid: int(days)
        for uid, days in db.execute(
            select(UserVisit.user_id, func.count())
            .where(UserVisit.day >= srs.day_key(since))
            .group_by(UserVisit.user_id)
        ).all()
    }
    opens: dict[str, dict[str, int]] = {}
    open_at: dict[str, datetime] = {}
    for uid, kind, times, last in db.execute(
        select(
            PreviewOpen.user_id,
            PreviewOpen.kind,
            func.sum(PreviewOpen.count),
            func.max(PreviewOpen.last_at),
        ).group_by(PreviewOpen.user_id, PreviewOpen.kind)
    ).all():
        opens.setdefault(uid, dict.fromkeys(PREVIEW_OPEN_KINDS, 0))[kind] = int(times or 0)
        open_at[uid] = _latest(last, open_at.get(uid))
    web_lectures = _lecture_counts(db, PRE_KEYS, MAIN_KEYS)
    grab_lectures = _lecture_counts(db, GRAB_KEYS)
    touched = _lecture_counts(db, PRE_KEYS, MAIN_KEYS, GRAB_KEYS)

    rows: list[dict[str, Any]] = []
    for profile in db.scalars(select(Profile)).all():
        uid = profile.id
        pre_card_count, pre_card_at = pre_cards.get(uid, (0, None))
        main_card_count, main_card_at = main_cards.get(uid, (0, None))
        grab_kinds, grab_clicks, grab_at = grabs.get(uid, (0, 0, None))
        preview_count, preview_at = previews.get(uid, (0, None))
        visit_days, visit_times, visit_at = visits.get(uid, (0, 0, None))
        last_at = _latest(pre_card_at, main_card_at, grab_at, preview_at, visit_at, open_at.get(uid))
        rows.append(
            {
                "id": uid,
                "email": profile.email,
                "isAdmin": profile.is_admin,
                # 0이 「안 썼다」인지 「못 썼다」인지를 가르는 값이다. 위를 보라.
                "hasAccess": uid in granted,
                "joinedAt": _iso(profile.created_at),
                "lastAt": _iso(last_at),
                "lectures": touched.get(uid, 0),
                # 편 수를 갈라 둔다 — 웹에서 푸는 사람과 받아 가는 사람은 다른 사람이다.
                "webLectures": web_lectures.get(uid, 0),
                "grabLectures": grab_lectures.get(uid, 0),
                "pre": {"cards": pre_card_count, "grades": pre_grades.get(uid, (0, None))[0]},
                "main": {"cards": main_card_count, "grades": main_grades.get(uid, (0, None))[0]},
                # 「지금 쓰고 있나」. 누적과 갈라 둔다 — 누적은 안 줄어든다.
                "recentCards": recent_cards.get(uid, 0),
                "recentGrades": pre_recent.get(uid, (0, None))[0] + main_recent.get(uid, (0, None))[0],
                # 접속. **0 은 「안 들어왔다」가 아닐 수 있다** — `visitsSince` 를 보라.
                "visits": {
                    "days": visit_days,
                    "times": visit_times,
                    "recentDays": recent_days.get(uid, 0),
                    "lastAt": _iso(visit_at),
                },
                # 우리 화면에서 예습 링크를 누른 횟수. 갈래로 갈라 둔다.
                "opens": opens.get(uid, dict.fromkeys(PREVIEW_OPEN_KINDS, 0)),
                # `clicks` 는 내려받은 횟수가 아니라 누른 횟수다. 위를 보라.
                "grabs": {"kinds": grab_kinds, "clicks": grab_clicks},
                # **개인 예습 대화다**(`user_preview`). 기본 링크는 강의당 하나이고
                # 반 전체가 같은 것을 읽으므로 사람별로 셀 수 있는 것이 아니다 — 윗글을 보라.
                # 관리자가 기본 링크를 만들면 그 `/c/` 가 자기 줄로도 남아 여기 섞인다.
                "previews": preview_count,
                # 각자 고쳐 쓰는 예습 프롬프트. 비어 있으면 화면의 기본 문구를 쓴다.
                "prompt": {
                    "custom": bool(profile.preview_prompt.strip()),
                    "chars": len(profile.preview_prompt.strip()),
                },
            }
        )

    # 쓰는 사람이 위, 한 번도 안 연 사람이 아래. 안 연 사람끼리는 가입 순이라
    # **승인하고 안 들어온 사람이 맨 밑에 모인다.**
    active = sorted((row for row in rows if row["lastAt"]), key=lambda row: row["lastAt"], reverse=True)
    idle = sorted((row for row in rows if not row["lastAt"]), key=lambda row: row["joinedAt"] or "")

    return {
        "now": now.isoformat(),
        "recentDays": RECENT_DAYS,
        # **언제부터 남았는가.** 이 값이 없으면 화면이 0을 「안 했다」로 그린다.
        "visitsSince": _iso(db.scalar(select(func.min(UserVisit.first_at)))),
        "opensSince": _iso(db.scalar(select(func.min(PreviewOpen.first_at)))),
        "users": active + idle,
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
            "grabs": [],
            "preview": False,
            # 우리 화면에서 이 편의 링크를 누른 횟수. 갈래로 갈라 둔다.
            "opens": dict.fromkeys(PREVIEW_OPEN_KINDS, 0),
            "lastAt": None,
        }

    lectures: dict[tuple[str, str], dict[str, Any]] = {}

    def slot(subject: str, run_id: str) -> dict[str, Any]:
        return lectures.setdefault((subject, run_id), empty())

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
            row["lastAt"] = _iso(_latest(last, _parse(row["lastAt"])))

    for subject, run_id, kind, last in db.execute(
        select(AssetGrab.subject, AssetGrab.run_id, AssetGrab.kind, AssetGrab.last_at).where(
            AssetGrab.user_id == user_id
        )
    ).all():
        row = slot(subject, run_id)
        row["grabs"].append(kind)
        row["lastAt"] = _iso(_latest(last, _parse(row["lastAt"])))

    for subject, run_id, kind, times, last in db.execute(
        select(
            PreviewOpen.subject, PreviewOpen.run_id, PreviewOpen.kind, PreviewOpen.count, PreviewOpen.last_at
        ).where(PreviewOpen.user_id == user_id)
    ).all():
        row = slot(subject, run_id)
        if kind in PREVIEW_OPEN_KINDS:
            row["opens"][kind] = int(times or 0)
        row["lastAt"] = _iso(_latest(last, _parse(row["lastAt"])))

    for subject, run_id, last in db.execute(
        select(UserPreview.subject, UserPreview.run_id, UserPreview.updated_at).where(
            UserPreview.user_id == user_id, UserPreview.conversation_url != ""
        )
    ).all():
        row = slot(subject, run_id)
        row["preview"] = True
        row["lastAt"] = _iso(_latest(last, _parse(row["lastAt"])))

    titles = {
        (lecture.subject, lecture.run_id): lecture
        for lecture in db.scalars(select(Lecture)).all()
    }
    out = []
    for (subject, run_id), row in lectures.items():
        lecture = titles.get((subject, run_id))
        row["grabs"].sort()
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
    }
