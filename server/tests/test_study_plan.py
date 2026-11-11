"""시험별 하루 목표: 날짜 경계, 고정된 하루 목표, 신규 강의 분량, 시험 범위·사용자 격리.

2026-11-11부터 강의 점수는 Main-Quiz 학습률(root_learning/score.py)이고 도달 시각은 시험 48시간 전이다.
"""

from datetime import date, datetime, timedelta
from unittest.mock import patch

from tests.root_support import setup, publish, start, action, ADMIN
client, user, SessionLocal = setup()
from app.models import Lecture, TimetableEvent
from app.study_engine.memory import DAY_MS
from app.study_engine.planning import BUFFER_DAYS, KOREA, balanced_daily_gain, daily_plan, day_start, total_score

START = int(datetime(2026, 10, 6, 4, tzinfo=KOREA).timestamp() * 1000)  # 학습일 시작(새벽 4시)
NOW = START + 10 * 3_600_000
DEADLINE = START + 4 * DAY_MS + 9 * 3_600_000


def unit(level, studied_at=None, gain=.1, reviews=0, when=date(2026, 10, 5)):
    """망각하는 합성 강의: `until`까지 공부했으면 level+gain, 마지막 평가 뒤로 9일 척도로 깎인다."""
    def progress(until, at):
        studied = studied_at is not None and until >= studied_at
        anchor = studied_at if studied else START - 1000
        return (level + (gain if studied else 0)) / (1 + max(0, at - anchor) / DAY_MS / 9)
    return {"date": when, "progress": progress, "reviewsToday": reviews}


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
    assert balanced_daily_gain(20, 90, 1, [1.0] * 10) == 7
    assert day_start(NOW) == START and day_start(START - 1) == START - DAY_MS

    base = unit(.68)
    plan = daily_plan([base], 90, NOW, DEADLINE)
    assert BUFFER_DAYS == 2 and plan["bufferDays"] == 2
    assert plan["daysLeft"] == 5 and plan["forgettingLoss"] > 0
    assert plan["studyDeadline"] == DEADLINE - 2 * DAY_MS  # 시험 시작 48시간 전
    assert plan["learningDaysLeft"] == 3 and not plan["bufferPhase"]
    assert abs(plan["requiredGain"] - plan["netGain"] - plan["forgettingLoss"]) < .11
    assert plan["remainingGain"] > 0 and not plan["met"]
    studied = unit(.68, studied_at=NOW, reviews=1)
    after = daily_plan([studied], 90, NOW + 1, DEADLINE)
    assert after["endTarget"] == plan["endTarget"]  # 공부할 때마다 목표가 멀어지지 않는다.
    assert after["remainingGain"] < plan["remainingGain"]
    assert plan["progressPercent"] == 0 and plan["reviewedToday"] == 0
    assert after["progressPercent"] > plan["progressPercent"] and after["reviewedToday"] == 1
    complete = daily_plan([{"date": date(2026, 10, 5), "progress": lambda until, at: 1.0}], 90, NOW, DEADLINE)
    assert complete["met"] and complete["progressPercent"] == 100
    with patch("app.study_engine.planning.total_score", side_effect=[0, 0, 90, 89.99999, 100]):
        almost = daily_plan([base], 90, NOW, NOW + 3_600_000)
    assert not almost["met"] and almost["progressPercent"] == 99
    # 미준비·신규 예정 강의를 분모에 포함한다. 하나만 잘한 경우를 과대평가하지 않는다.
    incoming = {"date": date(2026, 10, 8), "progress": None, "reviewsToday": 0}
    with_new = daily_plan([base, incoming], 90, NOW, DEADLINE)
    assert with_new["currentScore"] < plan["currentScore"] and with_new["netGain"] > plan["netGain"]
    assert round(total_score([1, 0])) == 29
    no_materials = daily_plan([incoming], 90, NOW, DEADLINE)
    assert no_materials["limitedByMaterials"] and no_materials["availableCeiling"] == 0
    assert no_materials["assumedDailyRetention"] == .9 and no_materials["lateLectures"] == 1
    cutoff = DEADLINE - 2 * DAY_MS
    last_learning = daily_plan([base], 90, cutoff - 1, DEADLINE)
    assert last_learning["horizon"] == cutoff and last_learning["endTarget"] == 90
    assert not last_learning["bufferPhase"] and last_learning["learningDaysLeft"] == 1
    buffer = daily_plan([base], 90, cutoff, DEADLINE)
    assert buffer["bufferPhase"] and buffer["learningDaysLeft"] == 0
    assert buffer["morningScore"] < buffer["endTarget"] < 90  # 밀린 분량도 남은 여유 기간에 분산한다.
    exam_day = daily_plan([base], 90, NOW, NOW + 3_600_000)
    assert exam_day["daysLeft"] == 1 and exam_day["endTarget"] == 90 and exam_day["horizon"] == NOW + 3_600_000
    assert daily_plan([base], 80, NOW, DEADLINE)["endTarget"] <= plan["endTarget"]

    # ── API: Main-Quiz 학습 기록으로 계획한다 ─────────────────────────────────
    from tests.root_support import NOW as ROOT_NOW
    now_ms = int(ROOT_NOW.timestamp() * 1000)
    with SessionLocal() as db:
        for eid, when, category, course, title in [
            ("past", "2026-10-20", "lecture", "test", "지난 시험 범위"),
            ("past-exam", "2026-10-21", "exam", "test", "test 시험"),
            ("current", "2026-11-03", "lecture", "test", "현재 강의"),
            ("future", "2026-11-05", "lecture", "test", "새로 들어올 강의"),
            ("exam", "2026-11-09", "exam", "test", "test 시험"),
            ("unknown", "2026-11-10", "exam", "시험", "종합시험"),
            ("other", "2026-11-03", "lecture", "다른 과목", "다른 과목 강의"),
        ]:
            db.add(TimetableEvent(id=eid, date=date.fromisoformat(when), start_time="09:00", end_time="10:00",
                                  title=title, category=category, course=course))
        db.get(Lecture, ("test", "demo")).timetable_event_id = "current"
        db.commit()

    def plans(**params):
        with patch("app.routes.study_plan.now_ms", return_value=now_ms):
            response = client.get("/api/study-plan", params=params)
        assert response.status_code == 200, response.text
        return response.json()

    user("a")
    before = plans()
    assert len(before["plans"]) == 1 and before["unmatchedExams"] == ["종합시험"]
    first = before["plans"][0]
    assert first["lectureCount"] == 2 and first["unassessedLectures"] == 2  # Main-Quiz 공개 전
    assert first["currentScore"] == 0 and first["bufferDays"] == 2 and before["lectureGoal"] is None
    publish(client, user)
    published = plans()["plans"][0]
    assert published["unassessedLectures"] == 1 and published["currentScore"] == 0
    sid = start(client)
    assert action(client, sid, "r1", "reveal", attempted=True).status_code == 200
    assert action(client, sid, "g1", "rate", selfRating="Good").status_code == 200
    rated = plans()["plans"][0]
    assert rated["currentScore"] > 0 and rated["reviewedToday"] == 1 and rated["earnedGain"] > 0
    assert plans(subject="test", runId="demo")["plans"] == plans()["plans"]  # 풀이와 달력은 같은 목표
    assert plans(subject="test", runId="missing")["plans"] == []
    assert client.get("/api/study-plan?target=101").status_code == 422
    assert plans(target=80)["plans"][0]["target"] == 80
    user("b")  # 다른 사용자의 기록은 섞이지 않는다.
    assert plans()["plans"][0]["currentScore"] == 0
    user("admin", True)  # 공개를 멈추면 미준비(0)로 돌아간다.
    assert client.put(ADMIN + "/publication", json={"revision": "v1", "reviewed": True, "enabled": False}).status_code == 200
    user("a")
    assert plans()["plans"][0]["unassessedLectures"] == 2
    with patch("app.routes.study_plan.now_ms", return_value=now_ms + 30 * DAY_MS):
        assert client.get("/api/study-plan").json()["plans"] == []  # 시험 시작 이후 제외
    print("PASS: 48시간 전 도달, 망각 보충, 신규·미준비 0, Main-Quiz 기록, 시험 범위·사용자·공개 격리")


if __name__ == "__main__":
    main()
