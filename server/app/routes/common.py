from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Asset, AssetGrab, Lecture, PreItem, Preview, QuizAttempt
from app.naming import nfc
from app.storage import ObjectStorage, StorageNotConfigured

LectureKey = tuple[str, str]


def storage_or_503() -> ObjectStorage:
    """R2를 쓰는 경로에서만 부른다.

    아직 안 붙었으면 503으로 답한다. 500으로 터뜨리면 "서버가 고장났다"로
    읽히지만 실제로는 아직 안 켠 기능이고, 캘린더는 멀쩡히 돌고 있다.
    """
    try:
        return ObjectStorage()
    except StorageNotConfigured as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": "storage_unconfigured", "message": "파일 저장소가 아직 연결되지 않았습니다."},
        ) from exc


def lecture_or_404(db: Session, subject: str, run_id: str) -> Lecture:
    """`run_id`만으로는 못 찾는다. 과목이 없으면 같은 교시의 다른 과목이 걸린다."""
    lecture = db.get(Lecture, (nfc(subject), run_id))
    if lecture is None:
        raise HTTPException(status_code=404, detail="강의를 찾을 수 없습니다.")
    return lecture


def material_marks(db: Session, keys: list[LectureKey]) -> dict[LectureKey, dict[str, bool]]:
    """강의마다 무엇이 올라와 있는가. 캘린더 한 화면치를 한 번에 센다.

    **다섯 칸이 `CHECKLIST_ITEMS`와 하나씩 짝이다.** 관리자가 채우는 칸과 사용자가
    보는 점이 같은 어휘를 쓴다는 뜻이다 — 앞 셋(`notesPrev`·`preview`·`prequiz`)이
    예습 자리로, 뒤 둘(`notesCurrent`·`quiz`)이 복습 자리로 묶인다.

    **작년 필기와 올해 필기를 갈라 센다.** 전에는 둘을 `notes` 하나로 묶었는데,
    작년 필기는 강의 전에 예습으로 읽는 것이고 올해 필기는 강의 후에 복습으로
    받는 것이라 쓰이는 자리가 아예 다르다.

    **`quiz`는 본덱(`main_apkg`)만이다.** 두 덱은 목적 함수도 쓰는 시점도 달라서
    한 점에 겹치면 어느 쪽도 안 뜻하게 된다.

    파일이 실제로 무엇인지는 상세 화면이 보여 준다. 여기서는 "있다/없다"만
    알면 되므로 종류별 개수를 세고 버린다.
    """
    fields = ("notesPrev", "preview", "prequiz", "notesCurrent", "quiz")
    marks: dict[LectureKey, dict[str, bool]] = {
        key: dict.fromkeys(fields, False) for key in keys
    }
    if not keys:
        return marks

    subjects = {subject for subject, _ in keys}
    run_ids = {run_id for _, run_id in keys}

    def _touch(key: LectureKey, field: str) -> None:
        # 과목·run_id를 각각 IN으로 좁히면 교차곱이 섞여 들어온다. 실제로
        # 요청한 짝인지 여기서 한 번 더 거른다.
        if key in marks:
            marks[key][field] = True

    by_kind = {
        "notes_prev": "notesPrev",
        "notes_current": "notesCurrent",
        "pre_apkg": "prequiz",
        "main_apkg": "quiz",
    }
    asset_rows = db.execute(
        select(Asset.subject, Asset.run_id, Asset.kind)
        .where(Asset.subject.in_(subjects), Asset.run_id.in_(run_ids))
        .group_by(Asset.subject, Asset.run_id, Asset.kind)
    ).all()
    for subject, run_id, kind in asset_rows:
        field = by_kind.get(kind)
        if field:
            _touch((subject, run_id), field)

    item_rows = db.execute(
        select(PreItem.subject, PreItem.run_id, func.count())
        .where(PreItem.subject.in_(subjects), PreItem.run_id.in_(run_ids))
        .group_by(PreItem.subject, PreItem.run_id)
    ).all()
    for subject, run_id, count in item_rows:
        if count:
            _touch((subject, run_id), "prequiz")

    preview_rows = db.execute(
        select(Preview.subject, Preview.run_id, Preview.share_url).where(
            Preview.subject.in_(subjects), Preview.run_id.in_(run_ids)
        )
    ).all()
    for subject, run_id, share_url in preview_rows:
        if share_url:
            _touch((subject, run_id), "preview")

    return marks


# 받아 간 종류를 사용자 화면의 자리 둘로 묶는 표. 한 자리에 여러 종류가 붙으므로
# **하나만 받아도 그 자리는 채워진다** — 예습덱만 받고 작년 필기는 안 읽는 사람이
# 미완으로 남으면 안 된다.
GRAB_TRACKS = {"pre": ("notes_prev", "pre_apkg"), "main": ("notes_current", "main_apkg")}


def asset_grabs(db: Session, user_id: str, keys: list[LectureKey]) -> dict[LectureKey, set[str]]:
    """이 사람이 강의마다 어떤 종류를 받아 갔는가.

    **덱에서 "했다"를 아는 유일한 길이다.** apkg는 Anki에서 풀리므로 풀이 기록이
    서버에 없지만, 파일이 나가려면 서명을 받아 가야 하고 그 서명은 사용자가
    버튼을 눌러야 나간다. 그래서 이것은 *받아 갔다*지 *풀었다*가 아니다.
    """
    grabs: dict[LectureKey, set[str]] = {}
    if not keys:
        return grabs

    wanted = set(keys)
    rows = db.execute(
        select(AssetGrab.subject, AssetGrab.run_id, AssetGrab.kind).where(
            AssetGrab.user_id == user_id,
            AssetGrab.subject.in_({subject for subject, _ in keys}),
            AssetGrab.run_id.in_({run_id for _, run_id in keys}),
        )
    ).all()
    for subject, run_id, kind in rows:
        # 과목·run_id를 각각 IN으로 좁히면 교차곱이 섞여 들어온다.
        if (subject, run_id) in wanted:
            grabs.setdefault((subject, run_id), set()).add(kind)
    return grabs


def grab_tracks(kinds: set[str]) -> dict[str, bool]:
    """받아 간 종류 집합 → 자리 둘의 참/거짓."""
    return {track: any(kind in kinds for kind in members) for track, members in GRAB_TRACKS.items()}


def prequiz_progress(
    db: Session, user_id: str, keys: list[LectureKey]
) -> dict[LectureKey, dict[str, int]]:
    """웹 예습퀴즈를 몇 개까지 풀었는가. 캘린더 한 화면치를 한 번에 센다.

    **잴 수 있는 것은 이것뿐이다.** 본덱도 예습덱도 apkg로 나가면 Anki에서
    풀리므로 서버에 아무 기록이 안 남는다. 여기 `total`은 웹에서 풀 수 있는
    `pre_item` 수이고, `answered`는 그중 이 사람이 채점받은 수다.

    문항이 없는 강의는 아예 빼고 돌려준다 — `{"total": 0}`을 내려보내면
    화면이 "0개 중 0개 풀었다"를 그리게 된다.
    """
    progress: dict[LectureKey, dict[str, int]] = {}
    if not keys:
        return progress

    subjects = {subject for subject, _ in keys}
    run_ids = {run_id for _, run_id in keys}
    wanted = set(keys)

    total_rows = db.execute(
        select(PreItem.subject, PreItem.run_id, func.count())
        .where(PreItem.subject.in_(subjects), PreItem.run_id.in_(run_ids))
        .group_by(PreItem.subject, PreItem.run_id)
    ).all()
    for subject, run_id, count in total_rows:
        # 과목·run_id를 각각 IN으로 좁히면 교차곱이 섞여 들어온다.
        if (subject, run_id) in wanted and count:
            progress[(subject, run_id)] = {"total": int(count), "answered": 0}

    if not progress:
        return progress

    answered_rows = db.execute(
        select(QuizAttempt.subject, QuizAttempt.run_id, func.count())
        .where(
            QuizAttempt.user_id == user_id,
            QuizAttempt.subject.in_(subjects),
            QuizAttempt.run_id.in_(run_ids),
        )
        .group_by(QuizAttempt.subject, QuizAttempt.run_id)
    ).all()
    for subject, run_id, count in answered_rows:
        row = progress.get((subject, run_id))
        if row is not None:
            # 문항이 지워지고 시도만 남을 수 있다. 그때 100%를 넘겨 그리지 않는다.
            row["answered"] = min(int(count), row["total"])

    return progress
