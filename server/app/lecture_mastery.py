"""사용자별 강의 학습률을 읽기만 한다.

2026-11-11부터 사이트의 학습률은 Main-Quiz 하나다(`root_learning/score.py`).
Quiz Bank 학습도(`for_bank`)는 legacy 화면(`?legacy=1`의 은행 카탈로그)만 쓴다.
"""

import logging
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.bank_validation.publication import usable as bank_usable
from app.models import BankState, QuizBank
from app.root_learning import content as root_content
from app.root_learning import light
from app.root_learning.policy import configured_policy
from app.root_learning.score import DISPLAY_TARGET_SCALE, lecture_score
from app.study_engine import empty_state, now_ms
from app.study_engine.mastery import lecture_mastery

log = logging.getLogger(__name__)


def for_bank(row: QuizBank | None, state: BankState | None, *, is_admin: bool, now: int | None = None,
             bank: dict | None = None) -> dict | None:
    """Legacy Quiz Bank 학습도. 사이트 학습률에는 쓰지 않는다."""
    if (not row or (not is_admin and not row.open_to_students)
            or not bank_usable(row.bank, row.validation)):
        return None
    current = state.state if state and state.build_id == row.build_id else empty_state()
    return lecture_mastery(bank if bank is not None else row.bank, current, now=now_ms() if now is None else now)


def as_mastery(score: dict) -> dict | None:
    """화면용 모양. 지도 목표가 없으면 None(잴 것이 없다)."""
    if score["score"] is None:
        return None
    return {"status": score["status"], "score": score["score"], "scope": "main-quiz",
            "targetCount": score["targetCount"], "fullTargets": score["fullTargets"],
            "ratedTargets": score["ratedTargets"]}


def main_quiz_inputs(db: Session, keys: list[tuple[str, str]], user) -> dict[tuple[str, str], tuple[dict, list]]:
    """이 사용자에게 열린 Main-Quiz의 (현재 판 문서, 이 사용자의 이벤트)."""
    # 그림 바이트를 뺀 판별 사본(light.py). 원본 문서를 요청마다 읽던 것이 캘린더 학습률 시간의 거의 전부였다.
    rows = light.current_rows(db, root_content.published_for(db, keys, user))
    return {key: (row.document, root_content.events_for(db, *key, user.id)) for key, row in rows.items()}


def lecture_overviews(db: Session, user, keys: list[tuple[str, str]],
                      *, include_cards: bool = True, at: datetime | None = None) -> dict[tuple[str, str], dict]:
    """강의마다 {mastery, cardProgress}. Main-Quiz가 없는 강의는 싣지 않는다(학습률 없음)."""
    policy = configured_policy()
    if not keys or policy is None:
        return {}
    at = at or datetime.now(UTC)
    skip = root_content.optional_excluded(db, user.id)  # Optional 계산 제외(2026-11-13)
    result = {}
    for key, (doc, events) in main_quiz_inputs(db, keys, user).items():
        try:
            mastery = as_mastery(lecture_score(doc, events, policy, at, skip_optional=skip,
                                                target_scale=DISPLAY_TARGET_SCALE))  # 보이는 값만 절반 기준
        except Exception:  # 한 강의의 계산 실패가 시간표 전체를 깨지 않게 한다.
            log.exception("Main-Quiz 학습률 계산 실패 %s/%s", *key)
            mastery = None
        result[key] = {"mastery": mastery, "cardProgress": None}
    return result


def lecture_masteries(db: Session, user, keys: list[tuple[str, str]]) -> dict[tuple[str, str], dict | None]:
    return {key: value["mastery"] for key, value in lecture_overviews(db, user, keys, include_cards=False).items()}
