"""강의 학습도 집계와 사용자·공개·빌드 경계를 로컬 DB에서 확인한다."""

import copy
import os
import tempfile
from datetime import date
from pathlib import Path
from unittest.mock import patch

_TMP = Path(tempfile.mkdtemp(prefix="studyez-mastery-"))
os.environ.update(ENVIRONMENT="local-test", DATABASE_URL=f"sqlite:///{(_TMP / 'test.db').as_posix()}")

from fastapi.testclient import TestClient
from app.auth import APP_POLICY, ROLE_ADMIN, CurrentUser, get_current_user
from app.database import Base, SessionLocal, engine
from app.main import app
from app.models import BankState, Lecture, QuizBank, TimetableEvent
from app.study_engine import empty_state, record_review
from app.study_engine.engine import target_for
from app.study_engine.mastery import lecture_mastery
from tests.bank_fixtures import example_bank


@patch("app.lecture_mastery.now_ms", return_value=1019)
@patch("app.routes.bank.engine.now_ms", return_value=1019)
def main(_bank_clock, _mastery_clock):
    bank = example_bank()
    state = empty_state()
    initial = lecture_mastery(bank, state)
    assert initial["status"] == "not_started" and initial["score"] == 0
    assert initial["totalDirections"] == 1  # 심화와 문제 없는 방향 제외
    for i in range(20):
        state = record_review(bank, state, "Q1", "Good", 1000 + i)
    mastered = lecture_mastery(bank, state)
    assert mastered["score"] == 100 and mastered["weakConcepts"] == 0
    lower = record_review(bank, state, "Q1", "Again", 2000)
    assert lecture_mastery(bank, lower)["status"] == "needs_review"
    near = copy.deepcopy(state)
    near["dimensions"]["C1:direct"]["mastery"] = target_for(bank, bank["questions"][0])["effective"] - 0.00001
    assert lecture_mastery(bank, near)["score"] == 99

    larger = copy.deepcopy(bank)
    larger["concepts"].append({**bank["concepts"][0], "concept_id": "C2", "title": "미학습 개념"})
    larger["questions"].append({**bank["questions"][0], "question_id": "Q4", "concept_id": "C2"})
    # 같은 개념·방향의 문제 수가 많아져도 점수는 올라가지 않는다.
    larger["questions"] += [{**bank["questions"][0], "question_id": f"dup-{i}"} for i in range(10)]
    mixed = lecture_mastery(larger, state)
    assert mixed["score"] == 29 and mixed["weakConcepts"] == 1
    assert mixed["weakest"][0]["conceptId"] == "C2"

    def score(first, second):
        profile = empty_state()
        for cid, q, progress in [("C1", larger["questions"][0], first),
                                 ("C2", larger["questions"][3], second)]:
            profile["dimensions"][f"{cid}:direct"] = {
                "mastery": target_for(larger, q)["effective"] * progress, "reviews": 1,
            }
        return lecture_mastery(larger, profile)["score"]

    # 평균이 같아도 고르게 아는 편을 높게 평가하고, 약점 보완의 영향이 더 크다.
    assert score(0.5, 0.5) == 50 > score(1, 0) == 29
    assert score(0.3, 0.8) - score(0.2, 0.8) > score(0.2, 0.9) - score(0.2, 0.8)
    assert score(0.2, 0.8) == score(0.8, 0.2)
    assert score(0, 0) == 0 and score(1, 1) == 100
    assert score(0.7, 0.7) == 70
    assert score(2, 0) == score(1, 0)  # 이미 목표를 넘긴 개념으로 빈틈을 메우지 못한다.
    for step in range(1, 11):
        assert score(step / 10, 0.5) >= score((step - 1) / 10, 0.5)
    assert lecture_mastery({**bank, "questions": []}, state) is None
    no_core = {**bank, "questions": [q for q in bank["questions"] if q["tier"] != "Core"]}
    assert lecture_mastery(no_core, state)["scope"] == "all"
    assert lecture_mastery(no_core, state)["status"] == "not_started"

    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        db.add(TimetableEvent(id="event", date=date(2026, 10, 2), start_time="09:00", end_time="10:00",
                              title="예시", category="lecture", course="예시"))
        db.add(Lecture(subject="subject", run_id="run", uid="test", date=date(2026, 10, 2), slot=1,
                       slot_end=1, start_time="09:00", title="예시", timetable_event_id="event"))
        db.commit()
        db.add(QuizBank(subject="subject", run_id="run", build_id="v1", status="ready", bank=bank,
                        validation={"pass": True}, open_to_students=True))
        db.add(BankState(user_id="one", subject="subject", run_id="run", build_id="v1", state=state))
        db.commit()

    client = TestClient(app)

    def login(uid):
        app.dependency_overrides[get_current_user] = lambda: CurrentUser(
            id=uid, email=f"{uid}@example.com", is_admin=False, apps=dict.fromkeys(APP_POLICY, ROLE_ADMIN))

    def summaries():
        detail = client.get("/api/lectures/subject/run")
        timetable = client.get("/api/timetable")
        assert detail.status_code == timetable.status_code == 200
        lecture = timetable.json()["events"][0]["lectures"][0]
        p = lecture["cardProgress"]
        if lecture["mastery"] is None:
            assert p is None
        else:
            assert p["total"] == 3
            assert sum(p[k] for k in ("unseen", "recognized", "retrieving", "retained")) == 3
        return detail.json()["mastery"], timetable.json()["events"][0]["lectures"][0]["mastery"]

    login("one")
    assert summaries() == (mastered, mastered)
    assert client.get("/api/lectures/subject/run/bank").json()["mastery"] == mastered
    later = 1019 + 9 * 86_400_000
    expected = lecture_mastery(bank, state, now=later)
    assert expected["score"] < mastered["score"] and expected["status"] == "needs_review"
    with patch("app.lecture_mastery.now_ms", return_value=later), patch("app.routes.bank.engine.now_ms", return_value=later):
        assert summaries() == (expected, expected)
        response = client.get("/api/lectures/subject/run/bank").json()
        assert response["mastery"] == expected
        assert response["conceptMap"][0]["directions"][0]["mastery"] < state["dimensions"]["C1:direct"]["mastery"]
    with SessionLocal() as db:
        assert db.get(BankState, ("one", "subject", "run")).state == state
    login("two")
    assert summaries() == (initial, initial)
    assert client.get("/api/timetable").json()["events"][0]["lectures"][0]["cardProgress"]["seen"] == 0
    login("one")
    with SessionLocal() as db:
        db.get(QuizBank, ("subject", "run")).build_id = "v2"
        db.commit()
    assert summaries() == (initial, initial)
    assert client.get("/api/timetable").json()["events"][0]["lectures"][0]["cardProgress"]["seen"] == 0
    # GET은 기존 기록을 수정하지 않는다.
    with SessionLocal() as db:
        assert db.get(BankState, ("one", "subject", "run")).build_id == "v1"
        db.get(QuizBank, ("subject", "run")).open_to_students = False
        db.commit()
    assert summaries() == (None, None)
    assert client.get("/api/lectures/subject/run/bank").status_code == 404
    with SessionLocal() as db:
        row = db.get(QuizBank, ("subject", "run"))
        row.open_to_students = True
        row.validation = {"pass": False}
        db.commit()
    assert summaries() == (None, None)
    print("PASS: 강의 학습도 계산, 미학습 개념, 사용자 격리, 재생성, 공개 범위, GET 무변경")


if __name__ == "__main__":
    main()
