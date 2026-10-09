"""Per-user overrides, shared-bank isolation and stale-source protection."""
import os
import tempfile
from pathlib import Path

tmp = Path(tempfile.mkdtemp(prefix="studyez-personal-"))
os.environ.update(ENVIRONMENT="local-test", DATABASE_URL=f"sqlite:///{(tmp / 'test.db').as_posix()}",
                  STUDYEZ_LOCAL_STORAGE_DIR=str(tmp / "storage"))

import copy
from datetime import date
from fastapi.testclient import TestClient
from app.auth import APP_POLICY, ROLE_ADMIN, CurrentUser, get_current_user
from app.database import Base, SessionLocal, engine
from app.main import app
from app.models import BANK_READY, BankFeedback, BankPersonalEdit, BankState, Lecture, QuizBank
from tests.bank_fixtures import example_bank

Base.metadata.create_all(engine)
bank = example_bank()
with SessionLocal() as db:
    db.add(Lecture(subject="test", run_id="demo", uid="demo", date=date(2026, 10, 9), slot=1,
                   slot_end=1, start_time="09:00", title="test", professors=[], author="", version=1))
    db.flush()
    db.add(QuizBank(subject="test", run_id="demo", build_id="build-1", bank=bank,
                    status=BANK_READY, validation={"pass": True}, open_to_students=True))
    db.commit()
client = TestClient(app)
base = "/api/lectures/test/demo/bank"

def user(uid, admin=False):
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id=uid, email=f"{uid}@example.com", is_admin=admin, apps=dict.fromkeys(APP_POLICY, ROLE_ADMIN))

def check(label, ok):
    assert ok, label
    print("PASS", label)

user("a")
served = client.post(base + "/next").json()
qid, token = served["question"]["question_id"], served["reviewToken"]
path = base + f"/questions/{qid}/personal"
snapshot = client.get(path).json()
draft = {"revision": snapshot["revision"], "question": "내 발문", "answer": "내 정답",
         "report": True, "category": "wording", "comment": "문장을 명확히 바꿨습니다."}
response = client.put(path, json=draft)
check("approved student can save personal wording and answer", response.status_code == 200)
check("personal prose replaces old scoring fields", response.json()["answer"]["answerUnits"] == []
      and response.json()["answer"]["personalAnswer"])
check("current question refresh uses the private wording", client.post(base + "/next").json()["question"]["question"] == "내 발문")
check("prepare uses private answer without revealing", client.post(base + "/prepare", json={"reviewToken": token}).json()["answer"] == "내 정답")
with SessionLocal() as db:
    check("editing and prepare do not reveal or grade", not db.get(BankState, ("a", "test", "demo")).state["served"]["revealed"])
    check("shared bank is unchanged", db.get(QuizBank, ("test", "demo")).bank == bank)
    feedback = db.query(BankFeedback).one()
    check("feedback includes proposal and comment", feedback.user_id == "a" and "내 정답" in feedback.comment
          and "문장을 명확히" in feedback.comment)
user("b")
check("another user reads the original", client.get(path).json()["draft"] == snapshot["original"])
check("another user cannot read a private comment", client.get(path).json()["comment"] == "")
other = client.post(base + "/next").json()
check("another user's displayed question is unchanged", other["question"]["question"] != "내 발문")
response = client.put(path, json={**draft, "report": False, "question": "B 발문", "answer": "B 정답"})
check("another user has an independent edit", response.status_code == 200 and client.get(path).json()["draft"]["answer"] == "B 정답")
user("a")
revealed = client.post(base + "/reveal", json={"reviewToken": token})
check("reveal shows private answer", revealed.json()["answer"] == "내 정답")
check("personal question can be rated normally", client.post(base + "/rate", json={"reviewToken": token, "rating": "Good"}).status_code == 200)
undone = client.post(base + "/undo", json={"reviewToken": token})
check("undo restores private wording and answer", undone.status_code == 200
      and undone.json()["question"]["question"] == "내 발문" and undone.json()["answer"]["answer"] == "내 정답")
with SessionLocal() as db:
    row = db.get(QuizBank, ("test", "demo")); row.build_id = "build-2"; db.commit()
check("identical source rebuild retains private correction", client.get(path).json()["edited"])
reset = client.put(path, json={**draft, "action": "reset", "report": False})
check("reset restores shared text only for this user", reset.status_code == 200
      and reset.json()["question"]["question"] == snapshot["original"]["question"])
user("b")
check("A's reset does not reset B", client.get(path).json()["draft"]["answer"] == "B 정답")
check("private comment survives reopening", client.get(path).json()["comment"] == draft["comment"])
with SessionLocal() as db:
    reports = db.query(BankFeedback).order_by(BankFeedback.id).all()
    check("unchecked save still reaches the administrator", len(reports) == 2
          and reports[1].user_id == "b" and "B 정답" in reports[1].comment)
    check("explicit report is highlighted; automatic feedback is ordinary", reports[0].highlighted and not reports[1].highlighted)
other_id = next(q["question_id"] for q in bank["questions"] if q["question_id"] != qid)
other_path = base + f"/questions/{other_id}/personal"
other_snapshot = client.get(other_path).json()
client.put(other_path, json={"revision": other_snapshot["revision"], **other_snapshot["draft"],
                            "comment": "일반 피드백", "report": False})
user("admin", True)
board = client.get("/api/admin/bank-feedback").json()
check("highlighted open reports precede newer ordinary feedback", board["questions"][0]["questionId"] == qid)
check("administrator receives ordinary feedback metadata", any(not r["highlighted"]
      for g in board["questions"] for r in g["reports"]))
user("b")
with SessionLocal() as db:
    row = db.get(QuizBank, ("test", "demo")); updated = copy.deepcopy(row.bank)
    original = next(q for q in updated["questions"] if q["question_id"] == qid)
    original["answer"] = "공용 정답 업데이트"; row.bank = updated; db.commit()
check("old override does not cover a changed shared source", not client.get(path).json()["edited"])
check("stale editor cannot save over a changed source", client.put(path, json=draft).status_code == 409)
fresh = client.get(path).json()
check("blank wording is rejected", client.put(path, json={**draft, "revision": fresh["revision"], "question": " "}).status_code == 422)
with SessionLocal() as db:
    row = db.get(QuizBank, ("test", "demo")); row.open_to_students = False; db.commit()
check("unpublished bank cannot be read or edited by a student", client.get(path).status_code == 404
      and client.put(path, json=draft).status_code == 404)
print("ALL PASSED")
