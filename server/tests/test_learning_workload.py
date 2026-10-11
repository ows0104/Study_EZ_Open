"""Remaining work follows unique objectives and the fixed scoped day plan."""
import copy
import os
import tempfile
from pathlib import Path
from unittest.mock import patch
_TMP = Path(tempfile.mkdtemp(prefix="studyez-workload-"))
os.environ.update(ENVIRONMENT="local-test", DATABASE_URL=f"sqlite:///{(_TMP / 'test.db').as_posix()}")
from app.study_engine.learning import catalog_unit, workload
from app.study_engine.memory import DAY_MS

NOW = 1791676800000
def unit(key, questions=True):
    return {"key": key, "deadline": NOW + 10 * DAY_MS,
            "questions": [{"identity": key, "question_id": key, "role": "learning", "item_difficulty": 1}] if questions else []}

units = [unit("new"), unit("due"), unit("future"), unit("explanation", False)]
state = {"objectives": {"due": {"covered": True, "dueAt": NOW},
    "future": {"covered": True, "dueAt": NOW + DAY_MS},
    "explanation": {"covered": True, "dueAt": NOW - DAY_MS}}}
plan = {"entries": [{"key": "new", "lane": "new"}, {"key": "due", "lane": "review"},
    {"key": "future", "lane": "mixed"}, {"key": "elsewhere", "lane": "new"}],
    "completed": ["future", "elsewhere", "stale"], "activeSeconds": 20, "budgetSeconds": 300}
before = copy.deepcopy((units, state, plan))
result = workload(units + [units[0]], state, plan, NOW, 3)
assert result["unseen"] == 1 and result["dueReviews"] == 1
assert result["nextReviewAt"] == NOW + DAY_MS
assert result["firstPassTargetAt"] == NOW + 7 * DAY_MS
assert result["today"] == {"total": 3, "completed": 1, "remaining": 2, "new": 1, "review": 1, "deferred": 0}
assert workload(units[:1], state, plan, NOW, 3)["today"]["total"] == 1
assert workload([], state, plan, NOW, 3)["today"]["remaining"] == 0
# Acknowledgement changes both coverage and fixed-plan counts. Additional
# attempts/variants cannot add to either total, and undo restores the snapshot.
state["objectives"]["new"] = {"covered": True, "dueAt": NOW + 2 * DAY_MS}
plan["completed"].append("new")
after = workload(units, state, plan, NOW, 3)
assert after["unseen"] == 0 and after["today"]["remaining"] == 1
plan["activeSeconds"] = 300
stopped = workload(units, state, plan, NOW, 3)
assert stopped["today"]["remaining"] == 0 and stopped["today"]["deferred"] == 1
assert stopped["today"]["completed"] == 2 and stopped["dueReviews"] == 1
assert workload(units, state, None, NOW, 3)["today"] is None
units, state, plan = before
assert workload(units, state, plan, NOW, 3) == result
assert workload([{**u, "deadline": None} for u in units], state, plan, NOW, 3)["firstPassTargetAt"] is None
print("PASS unique coverage, scoped fixed-plan remaining, review dates, undo snapshots and time-budget deferral")

from app.database import Base, SessionLocal, engine
from app.learning_progress import lecture_progress
from app.models import QuizBank
from app.models.learning import LearningDay, LearningProfile
from tests.bank_fixtures import example_bank

Base.metadata.create_all(engine)
with SessionLocal() as db, patch("app.learning_progress.now_ms", return_value=NOW):
    bank = example_bank()
    live_units = catalog_unit("course", "lecture", "", bank, "")
    db.add(QuizBank(subject="course", run_id="lecture", bank=bank, validation={"pass": True}, open_to_students=True))
    saved_state = {"objectives": {live_units[0]["key"]: {"covered": True, "dueAt": NOW}}}
    db.add(LearningProfile(user_id="one", minutes=60, buffer_days=3, enabled=True, state=saved_state))
    db.commit()
    key = ("course", "lecture")
    before_plan = lecture_progress(db, "one", [key])[key]
    assert before_plan["workload"]["today"] is None and before_plan["workload"]["dueReviews"] == 1
    assert db.get(LearningDay, ("one", "2026-10-11")) is None
    assert lecture_progress(db, "another-user", [key]) == {}
    db.add(LearningDay(user_id="one", day="2026-10-11", plan={"entries": [
        {"key": u["key"], "lane": "new"} for u in live_units],
        "completed": [live_units[0]["key"]], "activeSeconds": 10, "budgetSeconds": 600}))
    db.commit()
    projected = lecture_progress(db, "one", [key])[key]
    assert projected["workload"]["today"]["remaining"] == len(live_units) - 1
    assert db.get(LearningProfile, "one").state == saved_state
    assert not db.dirty and not db.new
print("PASS calendar/panel projection shares remaining counts without creating a plan or importing another user's history")
