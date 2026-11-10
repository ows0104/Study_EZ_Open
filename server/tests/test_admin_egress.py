"""Overview keeps its results without repeatedly transferring bank/review JSON."""
import copy
import json
import os
import tempfile
from datetime import date
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="studyez-admin-egress-"))
os.environ.update(ENVIRONMENT="local-test", DATABASE_URL=f"sqlite:///{(_TMP / 'test.db').as_posix()}")

from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.dialects import postgresql

from app.admin_banks import _summary_rows
from app.bank_validation.coverage import bank_hash
from app.database import Base, SessionLocal, engine
from app.main import app
from app.models import Asset, Lecture, QuizBank
from app.routes.bank import summary
from tests.bank_fixtures import example_bank

ADMIN = {"Authorization": "Bearer local-test-token"}
KEY = ("local", "demo")


def main():
    Base.metadata.create_all(engine)
    bank = example_bank()
    validation = {
        "pass": False, "errors": ["review needed"],
        "publication": {"allowed": True, "bankHash": bank_hash(bank),
                        "structuralValidation": {"pass": True}, "hasUnresolved": True},
        "revision": {"round": 2},
        "coverage": {"bankHash": bank_hash(bank), "sourceFilename": "notes.pdf", "status": "verified",
                     "pages": [{"page": 2, "note": "check", "status": "unreadable", "points": []}]},
        "dropped": [{"question_id": "old-q", "errors": ["old"], "question": {"large": "original"}}],
        "externalEvidenceReview": {"history": "UNNEEDED_REPORT" * 100_000},
    }
    with SessionLocal() as db:
        lecture = Lecture(subject=KEY[0], run_id=KEY[1], uid="egress", date=date(2026, 10, 15),
                          slot=1, slot_end=1, start_time="09:00", title="Overview", professors=[])
        row = QuizBank(subject=KEY[0], run_id=KEY[1], bank=bank, validation=validation,
                       raw_response="UNNEEDED_ORIGINAL" * 100_000, open_to_students=True,
                       build_id="same-build", status="ready", share_url="https://chatgpt.com/share/test",
                       review={"counts": {"ok": 3, "doubt": 1, "wrong": 2}, "history": "large" * 100_000})
        db.add_all([lecture, row, Asset(id="notes", subject=KEY[0], run_id=KEY[1],
                    kind="notes_current", filename="notes.pdf", object_key="notes.pdf")])
        db.commit()
        expected = summary(db, lecture, row, is_admin=True)
        # The overview lists every lecture and leaves out the repair history; the
        # per-lecture admin summary keeps it.
        assert expected.pop("revision") == {"round": 2}

    captured = []
    def observe(conn, cursor, statement, parameters, context, executemany):
        captured.append((statement, parameters))
    event.listen(engine, "before_cursor_execute", observe)
    client = TestClient(app)
    def overview():
        captured.clear()
        response = client.get("/api/admin/overview", headers=ADMIN)
        assert response.status_code == 200, response.text
        return response.json()["lectures"][0]

    first = overview()
    assert first["bank"] == expected, (first["bank"], expected)
    assert first["checklist"]["bank"] == "done"
    cold_queries = list(captured)
    assert not any("quiz_bank.raw_response" in sql or "quiz_bank.pages" in sql or "quiz_bank.usage" in sql
                   for sql, _ in cold_queries)
    # validation is read in one pass, not once per key (each `->` re-parses a json column).
    assert any("json_each(quiz_bank.validation)" in sql for sql, _ in cold_queries)
    assert not any("JSON_EXTRACT(quiz_bank.validation" in sql for sql, _ in cold_queries)
    assert "UNNEEDED" not in json.dumps(first)
    assert "revision" not in first["bank"]

    second = overview()
    assert second == first
    warm_queries = list(captured)
    assert not any("quiz_bank.bank" in sql or "quiz_bank.validation" in sql or "quiz_bank.review" in sql
                   for sql, _ in warm_queries), warm_queries
    print("PASS: warm overview reads revision stamps, not bank/review JSON")

    # An in-place edit must invalidate even when build_id does not change.
    with SessionLocal() as db:
        row = db.get(QuizBank, KEY)
        row.validation = {**copy.deepcopy(validation), "publication": {"allowed": False}}
        db.commit()
    changed = overview()
    assert not changed["bank"]["usable"] and changed["checklist"]["bank"] == "todo"
    assert any("quiz_bank.bank" in sql for sql, _ in captured)
    # Mutating a response must never poison the cached object.
    changed["bank"]["dropped"][0]["errors"].append("local mutation")
    assert "local mutation" not in overview()["bank"]["dropped"][0]["errors"]

    with SessionLocal() as db:
        db.get(Asset, "notes").filename = "new-notes.pdf"
        db.commit()
    assert overview()["bank"]["coverage"]["status"] == "stale"
    with SessionLocal() as db:
        row = db.get(QuizBank, KEY)
        updated = copy.deepcopy(row.bank)
        updated["questions"].append({**copy.deepcopy(updated["questions"][0]), "question_id": "new"})
        row.bank = updated
        db.commit()
    assert overview()["bank"]["questionCount"] == len(bank["questions"]) + 1
    # A JSON-null validation (SQLAlchemy stores None as JSON null) reads as {} — never an error.
    with SessionLocal() as db:
        db.get(QuizBank, KEY).validation = None
        db.commit()
        expected_null = summary(db, db.get(Lecture, KEY), db.get(QuizBank, KEY), is_admin=True)
        expected_null.pop("revision")
    assert overview()["bank"] == expected_null
    with SessionLocal() as db:
        db.delete(db.get(QuizBank, KEY))
        db.commit()
    assert overview()["bank"] is None
    assert client.get("/api/admin/overview").status_code == 401
    compiled = str(_summary_rows([KEY]).compile(dialect=postgresql.dialect()))
    assert compiled.count("json_each(quiz_bank.validation)") == 1, compiled
    assert "quiz_bank.validation ->" not in compiled and "quiz_bank.raw_response" not in compiled
    assert "json_object_agg" in compiled and "json_typeof(quiz_bank.validation)" in compiled
    assert "'revision'" not in compiled and "revision" not in str(_summary_rows([KEY]).compile(
        dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
    event.remove(engine, "before_cursor_execute", observe)
    print("PASS: summary parity, JSON projection, edits, source changes, deletion, authorization, PostgreSQL SQL")


if __name__ == "__main__":
    main()
