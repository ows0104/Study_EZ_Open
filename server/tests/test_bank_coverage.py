"""기존 카드 보강의 권한·중복 요청·진도 보존·원문 변경 거절을 확인한다."""
import copy
import os
import tempfile
from datetime import UTC, date, datetime
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="studyez-coverage-"))
os.environ.update(ENVIRONMENT="local-test", DATABASE_URL=f"sqlite:///{(_TMP / 'bank.db').as_posix()}", RUNNER_TOKEN="runner-token")

from fastapi.testclient import TestClient
from sqlalchemy import select
from app.auth import APP_POLICY, ROLE_ADMIN, CurrentUser, get_current_user
from app.database import Base, SessionLocal, engine
from app.main import app
from app.models import Asset, BankState, BankStateArchive, BankVersion, Lecture, QuizBank, PrequizJob
from app.bank_edits import current_review
from app.bank_validation.coverage import bank_hash
from app.bank_validation.schema import without_retired
from app.study_engine import empty_state, now_ms, record_review
from app.study_retention import manifest
from tests.bank_fixtures import example_bank


def main():
    Base.metadata.create_all(engine)
    bank = without_retired(example_bank())
    bank["questions"][1].update(format="mcq", mcq_mode="comparison", question="목표 사실의 이름은?",
        options=[{"id": "A", "text": "예시 정답"}, {"id": "B", "text": "오답"}], correct_option_ids=["A"])
    at = datetime.now(UTC)
    state = record_review(bank, empty_state(), "Q1", "Good", now_ms())
    with SessionLocal() as db:
        db.add(Lecture(subject="local", run_id="demo", uid="demo#test", date=date(2026, 10, 13),
                       slot=1, slot_end=1, start_time="09:00", title="강의", professors=[], author=""))
        db.add(Asset(id="notes", subject="local", run_id="demo", kind="notes_current", filename="a.pdf",
                     object_key="a.pdf", content_type="application/pdf"))
        edits = {"Q2": {"action": "accept", "original": copy.deepcopy(bank["questions"][1]), "question": copy.deepcopy(bank["questions"][1])}}
        db.add(QuizBank(subject="local", run_id="demo", bank=bank, validation={"pass": True, "errors": [], "warnings": [], "edits": edits},
                        build_id="old-build", status="ready", responded_at=at, open_to_students=True, raw_response="raw"))
        db.add(BankState(user_id="learner", subject="local", run_id="demo", build_id="old-build", state=state))
        db.commit()
    client = TestClient(app)
    admin = CurrentUser(id="learner", email="admin@example.com", is_admin=True, apps=dict.fromkeys(APP_POLICY, ROLE_ADMIN))
    student = CurrentUser(id="learner", email="student@example.com", is_admin=False, apps=dict.fromkeys(APP_POLICY, ROLE_ADMIN))
    base = "/api/admin/lectures/local/demo"
    app.dependency_overrides[get_current_user] = lambda: student
    assert client.post(base + "/bank/audit").status_code == 403
    app.dependency_overrides[get_current_user] = lambda: admin
    runner = {"Authorization": "Bearer runner-token"}
    assert client.post(base + "/bank/runner-audit").status_code == 401
    assert client.post(base + "/bank/runner-audit", headers={"Authorization": "Bearer wrong"}).status_code == 401
    first = client.post(base + "/bank/runner-audit", headers=runner)
    second = client.post(base + "/bank/audit")
    assert first.status_code == 200 and first.json()["created"]
    assert second.json()["jobId"] == first.json()["jobId"] and not second.json()["created"]
    data = client.get(base + "/bank-response", headers=runner).json()
    assert data["existingBank"] == bank and data["baseBuildId"] == "old-build"
    enriched = copy.deepcopy(bank)
    enriched["questions"][1]["mcq_mode"] = "recall_first"
    enriched["questions"].append({**copy.deepcopy(bank["questions"][0]), "question_id": "SUP_Q1", "question": "새 사실?"})
    coverage = {"bankHash": bank_hash(enriched), "status": "verified", "gapCount": 0, "unreadablePages": 0, "sourceFilename": "a.pdf"}
    payload = {"respondedAt": data["respondedAt"], "baseBuildId": "old-build", "bank": enriched,
               "validation": {"pass": True, "errors": [], "warnings": [], "coverage": coverage}, "pages": {}}
    old_runner = {k: v for k, v in payload.items() if k != "baseBuildId"}
    assert client.put(base + "/bank", headers=runner, json=old_runner).status_code == 409
    bad = copy.deepcopy(payload)
    bad["bank"]["questions"][0]["answer"] = "바뀐 정답"
    assert client.put(base + "/bank", headers=runner, json=bad).status_code == 422
    stale = {**payload, "baseBuildId": "different"}
    assert client.put(base + "/bank", headers=runner, json=stale).status_code == 409
    good = client.put(base + "/bank", headers=runner, json=payload)
    assert good.status_code == 200 and good.json()["buildId"] == "old-build", good.text
    with SessionLocal() as db:
        current = db.get(BankState, ("learner", "local", "demo"))
        assert current.build_id == "old-build"
        # A safe transition adds provenance, but must retain every original
        # review fact, aggregate, and scheduling value. Full JSON equality
        # incorrectly rejects the new fingerprint/origin metadata.
        retained_history = copy.deepcopy(current.state["history"])
        assert len(retained_history) == len(state["history"])
        for original, retained in zip(state["history"], retained_history):
            assert {key: retained[key] for key in original} == original
            assert retained["origin_build_id"] == "old-build"
            assert retained["origin_question_id"] == original["question_id"]
            assert retained["origin_event_id"]
            assert retained["question_fingerprint"] == manifest(bank)[original["question_id"]]
        for key, original in state.items():
            if key != "history":
                assert current.state[key] == original, key
        assert current.state["_question_fingerprints"] == manifest(enriched)
        assert current.state["_study_build_id"] == "old-build"
        assert "SUP_Q1" not in current.state["items"]
        archives = list(db.scalars(select(BankStateArchive).where(
            BankStateArchive.user_id == "learner", BankStateArchive.subject == "local",
            BankStateArchive.run_id == "demo", BankStateArchive.build_id == "old-build")))
        assert any(archive.state == state for archive in archives)
        versions = list(db.scalars(select(BankVersion).where(
            BankVersion.subject == "local", BankVersion.run_id == "demo", BankVersion.build_id == "old-build")))
        assert any(version.bank == bank for version in versions)
        assert any(version.bank == enriched for version in versions)
        assert db.get(QuizBank, ("local", "demo")).bank["questions"][1]["mcq_mode"] == "recall_first"
        assert db.get(QuizBank, ("local", "demo")).validation["edits"]["Q2"]["question"]["mcq_mode"] == "recall_first"
        review = {"reviews": [{"question_id": "Q2", "verdict": "ok"}]}
        assert current_review(review, db.get(QuizBank, ("local", "demo")).validation)["reviews"] == review["reviews"]
    student_read = client.get("/api/lectures/local/demo/bank").json()
    assert student_read["summary"]["coverage"]["status"] == "verified"
    assert student_read["lectureGoal"]["unlearnedRemaining"] == 3
    assert client.put(base + "/bank", headers=runner, json=payload).status_code == 409
    with SessionLocal() as db:
        row = db.get(QuizBank, ("local", "demo"))
        row.bank = {**row.bank, "warnings": ["변경됨"]}
        db.commit()
    assert client.get("/api/lectures/local/demo/bank").json()["summary"]["coverage"]["status"] == "stale"
    study = "/api/lectures/local/demo/bank/session/start"
    assert client.post(study, json={"size": 10, "continueAfterGoal": True}).status_code == 200
    assert client.post(study, json={"size": None, "dailyOnly": True}).json()["size"] is None
    with SessionLocal() as db:
        current = db.get(BankState, ("learner", "local", "demo"))
        assert not current.state["session"]["continue_after_goal"]
        assert current.state["history"] == retained_history
        db.get(PrequizJob, first.json()["jobId"]).state = "done"
        db.commit()
    assert client.post(base + "/bank/audit").status_code == 200
    retry_data = client.get(base + "/bank-response", headers=runner).json()
    failed = client.put(base + "/bank", headers=runner, json={"respondedAt": retry_data["respondedAt"], "baseBuildId": "old-build", "message": "일시적 실패"})
    assert failed.status_code == 200 and failed.json()["status"] == "ready"
    retry_data = client.get(base + "/bank-response", headers=runner).json()
    assert retry_data["baseBuildId"] == "old-build" and retry_data["existingBank"]
    assert client.put(base + "/bank", headers=runner, json={"respondedAt": retry_data["respondedAt"], "message": "구버전 재시도"}).status_code == 409
    print("PASS: coverage permissions, deduplication, append-only cards, stale upload rejection, progress preservation, stale audit")


if __name__ == "__main__":
    main()
