from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Asset, Lecture, PreItem, Preview, QuizAttempt
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
    """강의 칩에 찍을 점. 캘린더 한 화면치를 한 번에 센다.

    파일이 실제로 무엇인지는 상세 화면이 보여 준다. 여기서는 "있다/없다"만
    알면 되므로 종류별 개수를 세고 버린다.

    **`quiz`는 본덱(`main_apkg`)만이다.** 전에는 `pre_apkg`와 `pre_item`도 같은
    점을 켜서, 점만 보고는 시험 대비 덱이 올라왔는지 알 수 없었다. 두 덱은
    목적 함수도 쓰는 시점도 달라서 한 점에 겹치면 어느 쪽도 안 뜻하게 된다.
    """
    marks: dict[LectureKey, dict[str, bool]] = {
        key: {"notes": False, "quiz": False, "prequiz": False, "preview": False} for key in keys
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

    asset_rows = db.execute(
        select(Asset.subject, Asset.run_id, Asset.kind)
        .where(Asset.subject.in_(subjects), Asset.run_id.in_(run_ids))
        .group_by(Asset.subject, Asset.run_id, Asset.kind)
    ).all()
    for subject, run_id, kind in asset_rows:
        if kind in ("notes_current", "notes_prev"):
            _touch((subject, run_id), "notes")
        elif kind == "main_apkg":
            _touch((subject, run_id), "quiz")
        elif kind == "pre_apkg":
            _touch((subject, run_id), "prequiz")

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
