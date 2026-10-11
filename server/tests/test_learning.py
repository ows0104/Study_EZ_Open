"""Learning contract, bounded planning, durable evidence and public API boundaries."""
import copy
import os
import tempfile
from datetime import date
from pathlib import Path
from unittest.mock import patch

_TMP = Path(tempfile.mkdtemp(prefix="studyez-learning-"))
os.environ.update(ENVIRONMENT="local-test", DATABASE_URL=f"sqlite:///{(_TMP / 'test.db').as_posix()}")

from fastapi.testclient import TestClient
from app.auth import APP_POLICY, ROLE_ADMIN, CurrentUser, get_current_user
from app.database import Base, SessionLocal, engine
from app.main import app
from app.models import BankState, Lecture, QuizBank
from app.models.learning import LearningAttempt, LearningBankVersion, LearningProfile, LearningSession
from app.bank_validation.schema import without_retired
from app.bank_validation.learning import question_identity
from app.bank_validation.validate import validate_bank, validate_dropping
from app.learning_versions import archive_bank
from app.study_engine.learning import apply_attempt, build_plan, catalog_unit, choose_question
from app.study_engine.memory import DAY_MS
from app.study_engine.progress import panel_progress
from tests.bank_fixtures import example_bank

NOW = 1791676800000
USER = CurrentUser(id="learner", email="learn@example.com", is_admin=False, apps=dict.fromkeys(APP_POLICY, ROLE_ADMIN))


def learning_bank():
    bank = without_retired(example_bank())
    bank["build_meta"]["schema_version"] = "4.0"
    bank["questions"] = []
    for i in range(4):
        oid = f"U{i}"
        bank["learning_objectives"].append({"objective_id": oid, "concept_id": "C1", "title": f"요점 {i}",
            "target": f"관계 {i}를 구별한다", "kind": "fact" if i % 2 else "discrimination", "importance": 3,
            "rationale": "학습목표", "source_refs": [{"source_id": "S1", "locator": f"p{i+1}"}],
            "context": "큰 흐름", "explanation": "A와 B의 구별", "minimum": "A", "prerequisites": []})
        bank["coverage_inventory"].append({"title": f"범위 {i}", "source_refs": [{"source_id": "S1", "locator": f"p{i+1}"}],
            "status": "target", "reason": "학습목표", "objective_ids": [oid]})
        for role in ("learning", "variant", "exam"):
            q = without_retired(example_bank())["questions"][0]
            q.update(question_id=f"{oid}-{role}", format="mcq", question=f"{i} {role}: 올바른 관계는?",
                primary_objective_id=oid, supporting_objective_ids=[], role=role,
                recall_prompt="관계를 떠올려 보세요" if role == "learning" else "",
                options=[{"id": "A", "text": "관계 A"}, {"id": "B", "text": "관계 B"}], correct_option_ids=["A"],
                answer="A", answer_units=["A: 정답", "B: 오답"],
                option_explanations=[{"option_id": "A", "text": "A가 맞는 이유"}, {"option_id": "B", "text": "B가 다른 이유"}])
            bank["questions"].append(q)
    return bank


def main():
    bank = learning_bank()
    result = validate_bank(bank, ["S1"])
    assert result["pass"], result
    assert panel_progress(bank, {})["studyQuestionCount"] == 8
    assert validate_bank(example_bank(), ["S1"])["pass"]
    excluded = copy.deepcopy(bank)
    for field in ("concepts", "questions", "learning_objectives", "retrieval_plan"):
        excluded[field] = []
    excluded["coverage_inventory"] = [{"title": "도입 강의", "source_refs": [{"source_id": "S1", "locator": "p10"}],
        "status": "excluded", "reason": "교수가 이 시간은 시험 문제가 없다고 명시", "objective_ids": []}]
    assert validate_bank(excluded, ["S1"])["pass"]
    assert catalog_unit("course", "excluded", "도입 강의", excluded, "v") == []
    for field, value in (("source_refs", []), ("reason", ""), ("status", "target"),
                         ("source_refs", [{"source_id": "missing", "locator": "p10"}]),
                         ("objective_ids", ["missing"])):
        invalid = copy.deepcopy(excluded); invalid["coverage_inventory"][0][field] = value
        assert not validate_bank(invalid, ["S1"])["pass"], (field, value)
    invalid = copy.deepcopy(excluded); invalid["coverage_inventory"] = []
    assert not validate_bank(invalid, ["S1"])["pass"]
    bad = copy.deepcopy(bank); bad["questions"][0]["correct_option_ids"] = ["Z"]
    cleaned, result = validate_dropping(bad, ["S1"])
    assert result["pass"] and len(cleaned["learning_objectives"]) == 4 and len(cleaned["questions"]) == 11
    no_learning = copy.deepcopy(bank); no_learning["questions"] = [q for q in bank["questions"] if q["role"] == "exam"]
    result = validate_bank(no_learning, ["S1"])
    assert result["pass"] and any("미준비" in w for w in result["warnings"])
    broken = copy.deepcopy(bank); broken["coverage_inventory"].pop()
    assert not validate_bank(broken, ["S1"])["pass"]
    cycle = copy.deepcopy(bank)
    cycle["learning_objectives"][0]["prerequisites"] = ["U1"]
    cycle["learning_objectives"][1]["prerequisites"] = ["U0"]
    assert not validate_bank(cycle, ["S1"])["pass"]
    units = catalog_unit("course", "lecture", "제목", bank, "v", NOW + 10 * DAY_MS)
    integrated = copy.deepcopy(bank)
    next(q for q in integrated["questions"] if q["question_id"] == "U0-exam")["supporting_objective_ids"] = ["U1", "U2"]
    integrated_units = catalog_unit("course", "lecture", "제목", integrated, "v")
    partial = {"objectives": {u["key"]: {"covered": True} for u in integrated_units[:2]}}
    assert choose_question(integrated_units[0], partial, exam=True) is None
    partial["objectives"][integrated_units[2]["key"]] = {"covered": True}
    assert choose_question(integrated_units[0], partial, exam=True)["question_id"] == "U0-exam"
    assert choose_question(integrated_units[0], {}, exam=False)["role"] == "learning"
    plan = build_plan(units, {}, NOW, 5)
    assert plan["estimatedSeconds"] <= 300 and len({e["key"] for e in plan["entries"]}) == len(plan["entries"])
    assert any(e["lane"] == "new" for e in plan["entries"])
    multiple = units + catalog_unit("course", "lecture-2", "다른 강의", bank, "v", NOW + 10 * DAY_MS)
    shared_plan = build_plan(multiple, {}, NOW, 5)
    planned_lectures = {u["runId"] for u in multiple if u["key"] in {e["key"] for e in shared_plan["entries"]}}
    assert shared_plan["estimatedSeconds"] <= 300 and len(planned_lectures) == 2
    relabeled = copy.deepcopy(bank["questions"][0])
    relabeled["options"] = [{"id": "X", "text": "관계 B"}, {"id": "Y", "text": "관계 A"}]
    relabeled["correct_option_ids"], relabeled["answer"] = ["Y"], "Y. 관계 A"
    assert question_identity(relabeled) == question_identity(bank["questions"][0])
    variants = copy.deepcopy(bank)
    variants["questions"] += [{**q, "question_id": q["question_id"] + "-copy"} for q in bank["questions"]]
    assert build_plan(catalog_unit("course", "lecture", "제목", variants, "v"), {}, NOW, 5)["entries"] == plan["entries"]
    key = units[0]["key"]
    event = {"objectiveKey": key, "at": NOW, "correct": True, "confidence": "sure", "assisted": False, "seconds": 30}
    state = apply_attempt({}, event)
    assert apply_attempt(state, {**event, "at": NOW + 1000})["objectives"][key]["delayedSuccesses"] == 0
    assert apply_attempt(state, {**event, "at": NOW + DAY_MS})["objectives"][key]["delayedSuccesses"] == 1
    assert apply_attempt(state, {**event, "at": NOW + DAY_MS, "assisted": True})["objectives"][key]["delayedSuccesses"] == 0
    assert apply_attempt(state, {**event, "at": NOW + DAY_MS, "confidence": "guess"})["objectives"][key]["intervalDays"] == 1
    print("PASS contract, missing coverage, retained gaps, bounded deduplicated plans and delayed evidence")

    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        db.add(Lecture(subject="course", run_id="lecture", uid="lecture#제목", slot=1, slot_end=1,
                       start_time="09:00", title="제목", date=date(2026, 10, 1)))
        db.flush()
        db.add(QuizBank(subject="course", run_id="lecture", build_id="v1", bank=bank, validation={"pass": True}, open_to_students=True))
        db.add(Lecture(subject="course", run_id="excluded", uid="excluded#도입", slot=2, slot_end=2,
                       start_time="10:00", title="도입 강의", date=date(2026, 10, 1)))
        db.flush()
        db.add(QuizBank(subject="course", run_id="excluded", build_id="excluded-v1", bank=excluded,
                       validation={"pass": True}, open_to_students=True))
        db.commit()
    app.dependency_overrides[get_current_user] = lambda: USER
    client = TestClient(app)
    clock = [NOW]
    def post(path, body=None):
        response = client.post("/api/learning" + path, json=body or {})
        assert response.status_code == 200, (path, response.status_code, response.text)
        return response.json()
    def get(path):
        response = client.get("/api/learning" + path)
        assert response.status_code == 200, (path, response.text)
        return response.json()
    with patch("app.routes.learning.now_ms", side_effect=lambda: clock[0]):
        dash = get("/dashboard")
        assert dash["progress"]["total"] == 4 and dash["examQuestions"] == 0
        assert len(dash["scopeOnlyLectures"]) == 1
        assert get("/dashboard?subject=course&runId=lecture")["scopeOnlyLectures"] == []
        excluded_dash = get("/dashboard?subject=course&runId=excluded")
        assert excluded_dash["progress"]["total"] == 0 and excluded_dash["progress"]["covered"] == 0
        assert excluded_dash["scopeOnlyLectures"][0]["ranges"][0]["source_refs"][0]["locator"] == "p10"
        before_entries = dash["plan"]["entries"]
        sid = post("/sessions", {"mode": "daily"})["sessionId"]
        first = get(f"/sessions/{sid}"); token = first["token"]
        assert first["question"]["options"] == [] and "answer" not in first["question"] and not first["feedback"]
        assert get(f"/sessions/{sid}")["token"] == token
        first = post(f"/sessions/{sid}/action", {"token": token, "action": "options"})
        assert len(first["question"]["options"]) == 2
        for malformed in (None, [["A"]], "A"):
            assert client.post(f"/api/learning/sessions/{sid}/submit", json={"token": token,
                "confidence": "sure", "answer": {"selected": malformed}}).status_code == 422
        clock[0] += 30_000
        submission = {"token": token, "confidence": "guess", "answer": {"selected": ["A"]}, "activeSeconds": 30}
        answer = post(f"/sessions/{sid}/submit", submission)
        assert answer["feedback"]["correct"] is True and answer["feedback"]["confidence"] == "guess"
        post(f"/sessions/{sid}/submit", submission)
        assert get("/dashboard")["progress"]["covered"] == 0  # exposure alone != coverage
        second = post(f"/sessions/{sid}/acknowledge", {"token": token, "activeSeconds": 30})
        post(f"/sessions/{sid}/acknowledge", {"token": token})
        dash = get("/dashboard")
        assert dash["progress"]["covered"] == 1 and dash["plan"]["entries"] == before_entries
        assert dash["plan"]["activeSeconds"] == 30 and dash["examQuestions"] == 1
        with SessionLocal() as db:
            assert len(list(db.query(LearningAttempt))) == 1
        undone = post(f"/sessions/{sid}/undo")
        assert undone["token"] != token and undone["assisted"]
        assert get("/dashboard")["progress"]["covered"] == 0
        replay = post(f"/sessions/{sid}/submit", {**submission, "token": undone["token"]})
        post(f"/sessions/{sid}/acknowledge", {"token": replay["token"]})
        end = post(f"/sessions/{sid}/end")
        assert end["summary"]["completed"] == 1 and end["summary"]["freshGraded"] == 0
        print("PASS answer boundary, reload, idempotency, coverage acknowledgement and undo retaining exposure")

        exam = post("/sessions", {"mode": "exam", "count": 1})["sessionId"]
        shown = get(f"/sessions/{exam}")
        assert shown["optionsShown"] and len(shown["question"]["options"]) == 2
        assert client.post(f"/api/learning/sessions/{exam}/action", json={"token": shown["token"], "action": "help"}).status_code == 409
        clock[0] += 30_000
        tested = post(f"/sessions/{exam}/submit", {"token": shown["token"], "confidence": "sure", "answer": {"selected": ["A"]}, "activeSeconds": 30})
        assert tested["feedback"] is None
        result = post(f"/sessions/{exam}/acknowledge", {"token": shown["token"], "activeSeconds": 30})
        assert result["status"] == "complete" and result["summary"]["freshCorrect"] == 1 and result["results"][0]["answer"] == "A"
        assert get("/dashboard")["examQuestions"] == 0
        # Classic direct question endpoints must not reveal held-out questions.
        reserved_id = bank["questions"][2]["question_id"]
        assert client.get(f"/api/lectures/course/lecture/bank/questions/{reserved_id}/personal").status_code == 404
        print("PASS held-out exam requires prior learning, no help or answer leaks, release after finish, no reuse")

        # Abandoning a question spends the shared budget without awarding coverage.
        stop_sid = post("/sessions", {"mode": "daily"})["sessionId"]
        stopped_question = get(f"/sessions/{stop_sid}")
        spent_before = get("/dashboard")["plan"]["activeSeconds"]
        clock[0] += 45_000
        stopped = post(f"/sessions/{stop_sid}/end", {"token": stopped_question["token"], "activeSeconds": 45})
        assert stopped["seconds"] == 45 and stopped["summary"]["completed"] == 0
        post(f"/sessions/{stop_sid}/end", {"activeSeconds": 45})
        after_stop = get("/dashboard")
        assert after_stop["plan"]["activeSeconds"] == spent_before + 45 and after_stop["progress"]["covered"] == 1
        print("PASS unfinished time counts once without granting coverage")

        # Exact meaning survives IDs/rebuilds; source history remains archived.
        with SessionLocal() as db:
            row = db.get(QuizBank, ("course", "lecture"))
            archive_bank(db, row, clock[0])
            changed = copy.deepcopy(bank)
            changed["learning_objectives"][0]["objective_id"] = "RENAMED"
            changed["coverage_inventory"][0]["objective_ids"] = ["RENAMED"]
            for q in changed["questions"]:
                if q["primary_objective_id"] == "U0": q["primary_objective_id"] = "RENAMED"
            row.bank, row.build_id = changed, "v2"; db.commit()
        dash = get("/dashboard")
        assert dash["progress"]["covered"] == 1
        with SessionLocal() as db:
            assert db.query(LearningBankVersion).filter_by(run_id="lecture").count() == 2
        other = CurrentUser(id="other", email="other@example.com", is_admin=False, apps=dict.fromkeys(APP_POLICY, ROLE_ADMIN))
        app.dependency_overrides[get_current_user] = lambda: other
        assert client.get(f"/api/learning/sessions/{sid}").status_code == 404
        assert get("/dashboard")["progress"]["covered"] == 0
        app.dependency_overrides[get_current_user] = lambda: USER
        with SessionLocal() as db:
            row = db.get(QuizBank, ("course", "lecture")); row.open_to_students = False; db.commit()
        assert client.get(f"/api/learning/sessions/{exam}").status_code == 404
        print("PASS rebuild preservation, version archive, user isolation and revoked publication")
    print("ALL LEARNING CHECKS PASSED")


if __name__ == "__main__": main()
