from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Asset, Lecture, PreItem, Preview
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
        elif kind in ("main_apkg", "pre_apkg"):
            _touch((subject, run_id), "quiz")

    item_rows = db.execute(
        select(PreItem.subject, PreItem.run_id, func.count())
        .where(PreItem.subject.in_(subjects), PreItem.run_id.in_(run_ids))
        .group_by(PreItem.subject, PreItem.run_id)
    ).all()
    for subject, run_id, count in item_rows:
        if count:
            _touch((subject, run_id), "prequiz")
            _touch((subject, run_id), "quiz")

    preview_rows = db.execute(
        select(Preview.subject, Preview.run_id, Preview.share_url).where(
            Preview.subject.in_(subjects), Preview.run_id.in_(run_ids)
        )
    ).all()
    for subject, run_id, share_url in preview_rows:
        if share_url:
            _touch((subject, run_id), "preview")

    return marks
