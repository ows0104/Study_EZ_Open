"""날짜 경계, 고정된 하루 목표, 신규 강의 분량, 시험 범위·사용자 격리."""

import copy
import os
import tempfile
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

_TMP = Path(tempfile.mkdtemp(prefix="studyez-plan-"))
os.environ.update(ENVIRONMENT="local-test", DATABASE_URL=f"sqlite:///{(_TMP / 'test.db').as_posix()}")

from fastapi.testclient import TestClient
from app.auth import APP_POLICY, ROLE_ADMIN, CurrentUser, get_current_user
from app.database import Base, SessionLocal, engine
from app.main import app
from app.models import BankState, Lecture, QuizBank, TimetableEvent
from app.study_engine import empty_state, record_review
from app.study_engine.memory import DAY_MS
from app.study_engine.planning import KOREA, balanced_daily_gain, daily_plan, day_start, state_before, total_score
from tests.bank_fixtures import example_bank

START = int(datetime(2026, 10, 6, tzinfo=KOREA).timestamp() * 1000)
NOW = START + 10 * 3_600_000
DEADLINE = START + 4 * DAY_MS + 9 * 3_600_000


def main():
    # 같은 유지율로 계획대로 진행하면 재계산해도 확보량은 일정하고 순증가는 초반에 더 크다.
    level, target, retention = 20.0, 90.0, .9
    gain = balanced_daily_gain(level, target, retention, [1.0] * 10)
    increments = []
    for remaining_days in range(10, 0, -1):
        assert abs(balanced_daily_gain(level, target, retention, [1.0] * remaining_days) - gain) < 1e-9
        next_level = retention * level + gain
        increments.append(next_level - level)
        level = next_level
    assert abs(level - target) < 1e-9 and increments[0] > increments[-1]
    assert increments[0] > (90 - 20) / 10
    assert balanced_daily_gain(20, 90, 1, [1.0] * 10) == 7
    durations = [1.0, 1.0, .375]
    gain = balanced_daily_gain(20, 90, .9, durations)
    level = 20
    for dt in durations:
        level = .9 ** dt * level + gain * dt
    assert abs(level - 90) < 1e-9
    assert day_start(NOW) == START
    assert day_start(START - 1) == START - DAY_MS
    bank = example_bank()
    state = empty_state()
    state["dimensions"]["C1:direct"] = {"mastery": .68, "reviews": 5, "updated_at": START - 1000, "stability_days": 1}
    original = copy.deepcopy(state)
    unit = {"bank": bank, "state": state, "date": date(2026, 10, 5)}
    plan = daily_plan([unit], 90, NOW, DEADLINE)
    assert plan["daysLeft"] == 5 and plan["forgettingLoss"] > 0
    assert plan["studyDeadline"] == DEADLINE - 3 * DAY_MS
    assert plan["learningDaysLeft"] == 2 and not plan["bufferPhase"]
    assert plan["netGain"] > (90 - plan["morningScore"]) / 2
    assert abs(plan["requiredGain"] - plan["netGain"] - plan["forgettingLoss"]) < .11
    assert plan["remainingGain"] > 0 and not plan["met"]
    studied = record_review(bank, state, "Q1", "Good", NOW)
    after = daily_plan([{**unit, "state": studied}], 90, NOW + 1, DEADLINE)
    assert after["endTarget"] == plan["endTarget"]  # 공부할 때마다 목표가 멀어지지 않는다.
    assert after["remainingGain"] < plan["remainingGain"]
    assert plan["progressPercent"] == 0 and plan["reviewedToday"] == 0
    assert after["progressPercent"] > plan["progressPercent"] and after["reviewedToday"] == 1
    assert daily_plan([{**unit, "state": studied}], 90, START + DAY_MS, DEADLINE)["reviewedToday"] == 0
    complete_state = empty_state()
    for question in bank["questions"]:
        key = f'{question["concept_id"]}:{question["retrieval_direction"]}'
        complete_state["dimensions"][key] = {"mastery": 1, "reviews": 10, "updated_at": NOW, "stability_days": 100}
    complete = daily_plan([{**unit, "state": complete_state}], 90, NOW, DEADLINE)
    assert complete["met"] and complete["progressPercent"] == 100
    # 表示の丸めで未達成を100%にしない。
    with patch("app.study_engine.planning.total_score", side_effect=[0, 0, 90, 89.99999, 100]):
        almost = daily_plan([unit], 90, NOW, NOW + 3_600_000)
    assert not almost["met"] and almost["progressPercent"] == 99
    assert state_before(bank, studied, START)["dimensions"] == original["dimensions"]
    assert state == original
    # 기존 안정성이 없는 기록도 당일 평가 전의 가정을 정확히 복원한다.
    legacy = copy.deepcopy(state)
    legacy["dimensions"]["C1:direct"].pop("stability_days")
    before_legacy = daily_plan([{**unit, "state": legacy}], 90, NOW, DEADLINE)
    legacy = record_review(bank, legacy, "Q1", "Good", NOW)
    assert daily_plan([{**unit, "state": legacy}], 90, NOW, DEADLINE)["endTarget"] == before_legacy["endTarget"]
    # 배포 전후의 당일 기록이 섞여도 나중 평가의 before를 자정 상태로 오인하지 않는다.
    mixed = record_review(bank, empty_state(), "Q1", "Good", START - DAY_MS)
    past = state_before(bank, mixed, START)
    mixed = record_review(bank, mixed, "Q1", "Good", NOW)
    mixed["history"][-1].pop("dimension_before")
    mixed = record_review(bank, mixed, "Q1", "Good", NOW + 1000)
    assert state_before(bank, mixed, START)["dimensions"] == past["dimensions"]
    # 미준비·신규 예정 강의를 분모에 포함한다. 하나만 잘한 경우를 과대평가하지 않는다.
    incoming = {"bank": None, "state": empty_state(), "date": date(2026, 10, 8)}
    with_new = daily_plan([unit, incoming], 90, NOW, DEADLINE)
    assert with_new["currentScore"] < plan["currentScore"]
    assert with_new["netGain"] > plan["netGain"]
    assert round(total_score([1, 0])) == 29
    no_materials = daily_plan([incoming], 90, NOW, DEADLINE)
    assert no_materials["limitedByMaterials"] and no_materials["availableCeiling"] == 0
    assert no_materials["assumedDailyRetention"] == .9 and no_materials["lateLectures"] == 1
    cutoff = DEADLINE - 3 * DAY_MS
    last_learning = daily_plan([unit], 90, cutoff - 1, DEADLINE)
    assert last_learning["horizon"] == cutoff and last_learning["endTarget"] == 90
    assert not last_learning["bufferPhase"] and last_learning["learningDaysLeft"] == 1
    buffer = daily_plan([unit], 90, cutoff, DEADLINE)
    assert buffer["bufferPhase"] and buffer["learningDaysLeft"] == 0
    assert buffer["morningScore"] < buffer["endTarget"] < 90  # 밀린 분량도 남은 여유 기간에 분산한다.
    assert buffer["horizon"] == day_start(cutoff) + DAY_MS
    exam_day = daily_plan([unit], 90, NOW, NOW + 3_600_000)
    assert exam_day["daysLeft"] == 1 and exam_day["endTarget"] == 90 and exam_day["horizon"] == NOW + 3_600_000
    assert daily_plan([unit], 80, NOW, DEADLINE)["endTarget"] <= plan["endTarget"]

    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        for eid, when, category, course, title in [
            ("past", "2026-10-01", "lecture", "약물의 이해", "지난 시험 범위"),
            ("past-exam", "2026-10-02", "exam", "약물의 이해", "약물의 이해 시험"),
            ("current", "2026-10-05", "lecture", "약물의 이해", "현재 강의"),
            ("new", "2026-10-06", "lecture", "약물의 이해", "오늘 신규"),
            ("future", "2026-10-08", "lecture", "약물의 이해", "새로 들어올 강의"),
            ("exam", "2026-10-10", "exam", "약물의 이해", "약물의 이해 시험"),
            ("unknown", "2026-10-11", "exam", "시험", "종합시험"),
            ("other", "2026-10-05", "lecture", "다른 과목", "다른 과목 강의"),
            ("practical", "2026-10-06", "practice", "약물의 이해", "실습"),
        ]:
            db.add(TimetableEvent(id=eid, date=date.fromisoformat(when), start_time="09:00", end_time="10:00",
                                  title=title, category=category, course=course))
        db.add(Lecture(subject="subject", run_id="run", uid="test", date=date(2026, 10, 5), slot=1,
                       slot_end=1, start_time="09:00", title="현재 강의", timetable_event_id="current"))
        db.commit()
        db.add(QuizBank(subject="subject", run_id="run", build_id="v1", status="ready", bank=bank,
                        validation={"pass": True}, open_to_students=True))
        db.add(BankState(user_id="one", subject="subject", run_id="run", build_id="v1", state=state))
        db.commit()
    client = TestClient(app)
    assert client.get("/api/study-plan").status_code == 401

    def login(uid):
        app.dependency_overrides[get_current_user] = lambda: CurrentUser(
            id=uid, email=f"{uid}@example.com", is_admin=False, apps=dict.fromkeys(APP_POLICY, ROLE_ADMIN))

    login("one")
    with patch("app.routes.study_plan.now_ms", return_value=NOW):
        response = client.get("/api/study-plan")
        assert response.status_code == 200, response.text
        payload = response.json()
        assert len(payload["plans"]) == 1
        first = payload["plans"][0]
        scoped = client.get("/api/study-plan?subject=subject&runId=run").json()["plans"]
        assert scoped == payload["plans"]  # 풀이와 달력은 같은 시험 전체 목표를 쓴다.
        assert client.get("/api/study-plan?subject=subject&runId=missing").json()["plans"] == []
        assert first["lectureCount"] == 3 and first["newToday"] == first["upcomingLectures"] == 1
        assert first["unassessedLectures"] == 2 and first["currentScore"] > 0
        assert payload["unmatchedExams"] == ["종합시험"]
        assert client.get("/api/study-plan?target=101").status_code == 422
        assert client.get("/api/study-plan?target=80").json()["plans"][0]["target"] == 80
        goal_url = "/api/study-plan?subject=subject&runId=run"
        goal_before = client.get(goal_url).json()["lectureGoal"]
        assert goal_before["remaining"] == 1 and not goal_before["met"]
        with SessionLocal() as db:
            db.add(Lecture(subject="subject", run_id="following", uid="next-test", date=date(2026, 10, 6), slot=1,
                           slot_end=1, start_time="09:00", title="다음 강의", timetable_event_id="new"))
            db.commit()
            db.add(QuizBank(subject="subject", run_id="following", build_id="v1", status="ready", bank=bank,
                            validation={"pass": True}, open_to_students=True))
            db.add(BankState(user_id="one", subject="subject", run_id="following", build_id="v1", state=complete_state))
            db.commit()
        # 다른 강의 학습이 현재 강의의 남은 학습 단위를 줄이지 않는다.
        goal_after = client.get(goal_url).json()["lectureGoal"]
        assert goal_after["progressPercent"] == goal_before["progressPercent"]
        assert goal_after["reviewedToday"] == goal_before["reviewedToday"]
        assert goal_after["remaining"] == goal_before["remaining"]
        with SessionLocal() as db:
            db.get(BankState, ("one", "subject", "following")).state = empty_state()
            db.commit()
        assert client.get(goal_url).json()["lectureGoal"]["remaining"] == 1
        with SessionLocal() as db:
            db.get(QuizBank, ("subject", "following")).open_to_students = False
            db.commit()
        assert client.get(goal_url).json()["lectureGoal"]["remaining"] == 1
        login("two")
        assert client.get("/api/study-plan").json()["plans"][0]["currentScore"] == 0
        login("one")
        with SessionLocal() as db:
            assert db.get(BankState, ("one", "subject", "run")).state == original
        # 이 강의의 목표에 도달하면 next가 새 문항을 내기 전에 회차를 마친다.
        with SessionLocal() as db:
            db.get(BankState, ("one", "subject", "run")).state = complete_state
            db.commit()
        base = "/api/lectures/subject/run/bank"
        with patch("app.routes.bank.engine.now_ms", return_value=NOW):
            assert not client.get(base).json()["lectureGoal"]["met"]  # 숙련도가 높아도 미확인 단위는 남는다.
            assert client.post(f"{base}/session/start", json={}).status_code == 200
            first_question = client.post(f"{base}/next").json()
            token = first_question["reviewToken"]
            client.post(f"{base}/reveal", json={"reviewToken": token})
            client.post(f"{base}/rate", json={"reviewToken": token, "rating": "Again"})
            waiting = client.post(f"{base}/next").json()
            assert waiting["waiting"] and waiting["session"]["status"] == "active"
            assert waiting["lectureGoal"]["relearningRemaining"] == 1 and not waiting["lectureGoal"]["met"]
            with patch("app.routes.bank.engine.now_ms", return_value=NOW + 60_000):
                retry = client.post(f"{base}/next").json()
                assert retry["question"]["question_id"] == first_question["question"]["question_id"]
                client.post(f"{base}/reveal", json={"reviewToken": retry["reviewToken"]})
                client.post(f"{base}/rate", json={"reviewToken": retry["reviewToken"], "rating": "Good"})
            # 이후 관측도 마지막 평가보다 뒤여야 한다.
        with patch("app.routes.bank.engine.now_ms", return_value=NOW + 60_001):
            stopped = client.post(f"{base}/next").json()
            assert stopped["question"] is None and stopped["summary"]["reason"] == "lecture_goal_met"
            assert stopped["summary"]["reviewed"] == 2
            # 추가 학습은 사용자가 선택한 새 회차에만 허용한다.
            client.post(f"{base}/session/start", json={"continueAfterGoal": True})
            picked = {"question": bank["questions"][0], "days": 4, "ranked": []}
            with patch("app.routes.bank.engine.select_question", return_value=picked):
                extra = client.post(f"{base}/next").json()
            assert extra["question"] is not None
            assert client.post(f"{base}/next").json()["reviewToken"] == extra["reviewToken"]
        with SessionLocal() as db:
            db.get(QuizBank, ("subject", "run")).build_id = "v2"
            db.commit()
        assert client.get("/api/study-plan").json()["plans"][0]["currentScore"] == 0
        with SessionLocal() as db:
            db.get(QuizBank, ("subject", "run")).open_to_students = False
            db.commit()
        assert client.get("/api/study-plan").json()["plans"][0]["unassessedLectures"] == 3
    with patch("app.routes.study_plan.now_ms", return_value=DEADLINE):
        assert client.get("/api/study-plan").json()["plans"] == []  # 시험 시작 이후 제외
    print("PASS: 일일 목표 고정, 망각 보충, 신규 분량, 시험 범위, KST, 사용자·공개·빌드 격리")


if __name__ == "__main__":
    main()
