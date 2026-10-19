"""Quarantined cards can be repaired; decisions survive rebuilds without stale writes."""
from __future__ import annotations

import copy
import datetime
import os
import tempfile
from pathlib import Path

TMP = Path(tempfile.mkdtemp(prefix="studyez-bank-edits-"))
os.environ.update(ENVIRONMENT="local-test", DATABASE_URL=f"sqlite:///{(TMP / 'bank.db').as_posix()}",
                  STUDYEZ_LOCAL_STORAGE_DIR=str(TMP / "storage"), RUNNER_TOKEN="runner-token")

from fastapi.testclient import TestClient  # noqa: E402
from app.auth import APP_POLICY, ROLE_ADMIN, CurrentUser, get_current_user  # noqa: E402
from app.bank_validation.schema import without_retired  # noqa: E402
from app.bank_validation.validate import validate_dropping  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Asset, BankState, Lecture, QuizBank  # noqa: E402
from tests.bank_fixtures import example_bank  # noqa: E402

ADMIN_H = {"Authorization": "Bearer local-test-token"}
RUNNER = {"Authorization": "Bearer runner-token"}
BASE = "/api/lectures/test/261007_01"
ADMIN = "/api/admin/lectures/test/261007_01"


def main() -> None:
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        db.add(Lecture(subject="test", run_id="261007_01", uid="edit-test", date=datetime.date(2026, 10, 7),
                       slot=1, slot_end=1, start_time="09:00", title="Edit test", professors=[], author="", version=1))
        db.add(Asset(id="notes", subject="test", run_id="261007_01", kind="notes_current", filename="notes.pdf",
                     object_key="notes.pdf", content_type="application/pdf"))
        db.commit()
    client = TestClient(app)
    response = client.put(f"{ADMIN}/bank-response", headers=ADMIN_H,
                          json={"raw": "test " * 60 + "STUDYEZ_BANK_COMPLETE"}).json()
    bank = without_retired(example_bank())
    bank["questions"][2].update(question_id="CNS-C05", prerequisites=[])
    matching = copy.deepcopy(bank["questions"][1])
    matching.update(question_id="CNS-C36", question="Match each letter", format="matching",
                    source_refs=[{"source_id": "S1", "locator": "p7"}],
                    matching_left=["a", "b"], matching_right=["A", "B", "B"],
                    answer_pairs=[{"left": "a", "right": "A"}, {"left": "b", "right": "B"}])
    bank["questions"].append(matching)
    clean, validation = validate_dropping(bank, ["S1"])
    assert validation["pass"] and len(validation["dropped"]) == 2
    payload = {"respondedAt": response["respondedAt"], "bank": clean, "validation": validation,
               "review": {"counts": {"wrong": 1, "doubt": 1, "ok": 0}, "reviews": [
                   {"question_id": "Q1", "verdict": "wrong", "note": "original review", "suggested_answer": "new"},
                   {"question_id": "Q2", "verdict": "doubt", "note": "check", "suggested_answer": ""}]}}
    assert client.put(f"{ADMIN}/bank", headers=RUNNER, json=payload).status_code == 200

    def board() -> dict:
        answer = client.get("/api/admin/bank-review?subject=test&runId=261007_01&all=true", headers=ADMIN_H)
        assert answer.status_code == 200, answer.text
        return answer.json()["banks"][0]

    def card(qid: str) -> dict:
        return next(c for c in board()["cards"] if c["question"]["question_id"] == qid)

    def decide(qid: str, action: str, question: dict | None = None, expected: dict | None = None):
        group = board()
        current = next(c["question"] for c in group["cards"] if c["question"]["question_id"] == qid)
        return client.put(f"{ADMIN}/bank/cards/{qid}", headers=ADMIN_H,
                          json={"action": action, "question": question, "expectedQuestion": expected or current,
                                "buildId": group["buildId"]})

    flagged = client.get("/api/admin/bank-review", headers=ADMIN_H).json()
    assert flagged["open"] == 4
    assert "integration" in card("CNS-C05")["errors"][0]
    assert card("CNS-C36")["question"]["matching_right"] == ["A", "B", "B"]
    assert decide("CNS-C05", "accept").status_code == 422
    invalid = copy.deepcopy(card("CNS-C36")["question"])
    invalid["answer_pairs"][0]["right"] = "missing"
    assert decide("CNS-C36", "edit", invalid).status_code == 422
    assert len(board()["cards"]) == 4
    corrected = copy.deepcopy(card("CNS-C36")["question"])
    corrected["matching_right"] = ["A", "B"]
    saved = decide("CNS-C36", "edit", corrected)
    assert saved.status_code == 200, saved.text
    assert len(saved.json()["summary"]["dropped"]) == 1
    with SessionLocal() as db:
        assert db.get(QuizBank, ("test", "261007_01")).pages["CNS-C36"] == [7]
    foundation = copy.deepcopy(card("CNS-C05")["question"])
    foundation["prerequisites"] = ["Q1"]
    saved = decide("CNS-C05", "edit", foundation)
    assert saved.status_code == 200, saved.text
    assert saved.json()["summary"]["questionCount"] == 4
    assert saved.json()["summary"]["dropped"] == []
    assert card("CNS-C36")["edit"]["original"]["matching_right"] == ["A", "B", "B"]
    print("PASS: CNS-C05 foundation and CNS-C36 duplicate repair, atomic rejection and original preservation")

    inline = copy.deepcopy(card("Q2")["question"])
    inline.update(format="cloze", question="앞은 {A}, 뒤는 {B}, 다시 {A}다.",
                  answer="stale", answer_units=["stale"])
    saved = decide("Q2", "edit", inline)
    assert saved.status_code == 200, saved.text
    compiled = card("Q2")["question"]
    assert compiled["question"] == "앞은 {{c1}}, 뒤는 {{c1}}, 다시 {{c1}}다."
    assert compiled["answer_units"] == ["A", "B", "A"]
    assert compiled["answer"] == "앞은 A, 뒤는 B, 다시 A다."
    assert decide("Q2", "reset").status_code == 200
    print("PASS: inline cloze edits compile ordered answers and hide answers in stored stems")

    assert client.put(f"{ADMIN}/bank/open", headers=ADMIN_H, json={"open": True}).status_code == 200
    client.post(f"{BASE}/bank/session/start", headers=ADMIN_H, json={"size": 5})
    served = client.post(f"{BASE}/bank/next", headers=ADMIN_H).json()
    qid = served["question"]["question_id"]
    before = copy.deepcopy(card(qid)["question"])
    changed = {**before, "answer": "edited answer", "answer_units": ["edited answer"]}
    assert decide(qid, "edit", changed).status_code == 200
    assert decide(qid, "edit", {**changed, "answer": "stale"}, expected=before).status_code == 409
    with SessionLocal() as db:
        state = db.query(BankState).one()
        assert state.state["served"] is None
        assert state.state["session"]["status"] == "active"
    shown = client.post(f"{BASE}/bank/next", headers=ADMIN_H).json()
    if shown["question"]["question_id"] == qid:
        revealed = client.post(f"{BASE}/bank/reveal", headers=ADMIN_H,
                               json={"reviewToken": shown["reviewToken"]}).json()
        assert revealed["answer"] == "edited answer" and revealed["medicalReview"] is None
    old_build = board()["buildId"]
    assert client.put(f"{ADMIN}/bank", headers=RUNNER, json=payload).status_code == 200
    assert board()["buildId"] != old_build
    assert card("CNS-C05")["question"]["prerequisites"] == ["Q1"]
    assert card("CNS-C36")["question"]["matching_right"] == ["A", "B"]
    assert card(qid)["question"]["answer"] == "edited answer"
    print("PASS: stale writes rejected, in-flight tokens invalidated, same-source rebuild preserves corrections")

    assert decide("Q2", "accept").status_code == 200
    deleted = decide("Q1", "delete")
    assert deleted.status_code == 200, deleted.text
    assert any(d["questionId"] == "CNS-C05" for d in deleted.json()["summary"]["dropped"])
    assert client.put(f"{ADMIN}/bank", headers=RUNNER, json=payload).status_code == 200
    assert card("Q1")["edit"]["action"] == "delete"
    assert decide("Q1", "reset").status_code == 200
    assert not card("Q1")["edit"]
    assert decide("CNS-C36", "reset").status_code == 200
    assert card("CNS-C36")["errors"] and card("CNS-C36")["edit"] is None
    print("PASS: dependent quarantine, persistent exclusion, accept and undo decisions")

    new_bank = copy.deepcopy(bank)
    new_bank["questions"][2]["question"] = "New integration question"
    clean2, validation2 = validate_dropping(new_bank, ["S1"])
    assert client.put(f"{ADMIN}/bank", headers=RUNNER, json={**payload, "bank": clean2, "validation": validation2}).status_code == 200
    assert card("CNS-C05")["edit"] is None
    assert card("Q2")["edit"]["action"] == "accept"
    student = CurrentUser(id="student", email="s@test", is_admin=False, apps=dict.fromkeys(APP_POLICY, ROLE_ADMIN))
    app.dependency_overrides[get_current_user] = lambda: student
    assert client.get("/api/admin/bank-review").status_code == 403
    assert client.put(f"{ADMIN}/bank/cards/Q1", json={"action": "delete", "buildId": old_build,
                      "expectedQuestion": before}).status_code == 403
    public = client.get(f"{BASE}/bank").json()
    assert "dropped" not in public["summary"] and "edits" not in public
    app.dependency_overrides.clear()
    with SessionLocal() as db:
        row = db.get(QuizBank, ("test", "261007_01"))
        assert row.open_to_students
    print("PASS: rebuilt questions reopen review, unrelated decisions survive, student authorization and publication preserved")


if __name__ == "__main__":
    main()
