"""Exercise real APKG contents, publication gates, cache revisions and bundle integration."""
from __future__ import annotations

import copy
import io
import json
import os
import sqlite3
import tempfile
import zipfile
from datetime import UTC, date, datetime
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

_TMP = Path(tempfile.mkdtemp(prefix="studyez-bank-anki-test-"))
os.environ.update(ENVIRONMENT="local-test", DATABASE_URL=f"sqlite:///{(_TMP / 'test.db').as_posix()}",
                  STUDYEZ_LOCAL_STORAGE_DIR=str(_TMP / "storage"), PUBLIC_API_BASE_URL="http://testserver",
                  RUNNER_TOKEN="runner-token")

from fastapi.testclient import TestClient  # noqa: E402
from app.auth import APP_POLICY, ROLE_ADMIN, CurrentUser, get_current_user  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Asset, AssetGrab, BankState, Lecture, QuizBank  # noqa: E402
from app.storage import ObjectStorage  # noqa: E402
from tests.bank_fixtures import example_bank  # noqa: E402

SUBJECT, RUN = "검증과목", "261007_01"
URL = f"/api/lectures/{SUBJECT}/{RUN}/bank/anki"
BUNDLE = f"/api/bundles/decks/{SUBJECT}/{RUN}/main"
USER = CurrentUser(id="anki-student", email="s@example.com", is_admin=False,
                   apps=dict.fromkeys(APP_POLICY, ROLE_ADMIN))
ADMIN = {"Authorization": "Bearer local-test-token"}


def contents(payload: bytes) -> tuple[list, dict, dict, int]:
    with zipfile.ZipFile(io.BytesIO(payload)) as package:
        package.extract("collection.anki2", _TMP)
        media = json.loads(package.read("media"))
        assert all(package.read(slot) == b"image-bytes" for slot in media)
    with closing(sqlite3.connect(_TMP / "collection.anki2")) as connection:
        notes = connection.execute("SELECT guid, flds FROM notes ORDER BY id").fetchall()
        col = connection.execute("SELECT models, decks FROM col").fetchone()
        count = connection.execute("SELECT COUNT(*) FROM cards").fetchone()[0]
    return notes, json.loads(col[0]), media, count


def main() -> None:
    Base.metadata.create_all(engine)
    bank = example_bank()
    prototype = copy.deepcopy(bank["questions"][0])
    bank["questions"] = []
    for index, form in enumerate(("basic", "cloze", "list", "ox", "mcq", "multi_select", "matching", "sequence")):
        q = copy.deepcopy(prototype)
        q.update(question_id=f"Q{index + 1}", format=form, question=f"{form} <script>alert(1)</script>",
                 answer="정답과 해설", answer_units=["정답과 해설"])
        if form == "cloze":
            q.update(question="첫째 {{c1}}, 둘째 {{c2}}", answer_units=["비밀하나", "비밀둘"])
        if form in {"mcq", "multi_select"}:
            q.update(options=[{"id": "A", "text": "보기하나"}, {"id": "B", "text": "보기둘"}], correct_option_ids=["B"])
        if form == "matching":
            q.update(matching_left=["L1: 원인1", "L2: 원인2"], matching_right=["R1: 결과1", "R2: 결과2"],
                     answer_pairs=[{"left": "L1: 원인1", "right": "R1: 결과1"}, {"left": "L2: 원인2", "right": "R2: 결과2"}])
        if form == "sequence":
            q.update(sequence_items=["단계1", "단계2", "단계3"], correct_order=["단계1", "단계2", "단계3"])
        bank["questions"].append(q)
    reserved = copy.deepcopy(bank["questions"][4])
    reserved.update(question_id="Q-exam", role="exam", question="HELD_OUT_EXAM_SENTINEL")
    bank["questions"].append(reserved)
    bank["questions"][0].update(conflict_id="CF1", source_refs=[{"source_id": "EXT", "locator": "외부 근거"}])
    bank["source_conflicts"] = [{"conflict_id": "CF1", "description": "충돌 이유"}]
    with SessionLocal() as db:
        db.add(Lecture(subject=SUBJECT, run_id=RUN, uid="anki-test", date=date(2026, 10, 7), slot=1, slot_end=1,
                       start_time="09:00", title="Anki 검증", professors=[], author="", version=1))
        db.add(QuizBank(subject=SUBJECT, run_id=RUN, bank=bank, validation={"pass": True}, build_id="build1",
                        built_at=datetime.now(UTC), pages={"Q1": [1]}, status="ready",
                        review={"reviews": [{"question_id": "Q1", "verdict": "doubt", "note": "검토 메모",
                                             "suggested_answer": "대안 답"}]}))
        db.add(Asset(id="anki-slide", subject=SUBJECT, run_id=RUN, kind="bank_media", slide_no=1,
                     filename="slide.png", object_key="test/slide.png", size_bytes=11))
        db.add(Asset(id="anki-legacy", subject=SUBJECT, run_id=RUN, kind="main_apkg",
                     filename="legacy.apkg", object_key="test/legacy.apkg", size_bytes=6))
        db.add(AssetGrab(user_id=USER.id, subject=SUBJECT, run_id=RUN, kind="main_apkg", count=1))
        db.commit()
    ObjectStorage().put_bytes("test/slide.png", b"image-bytes")
    ObjectStorage().put_bytes("test/legacy.apkg", b"legacy")
    client = TestClient(app)
    assert client.get(URL).status_code == 401
    app.dependency_overrides[get_current_user] = lambda: USER
    assert client.get(URL).status_code == 404, "closed bank must not export"
    assert client.get(BUNDLE + "?exportId=guessed").status_code == 404
    closed_ref = {"decks": [{"subject": SUBJECT, "runId": RUN, "kind": "main", "exportId": "guessed"}]}
    assert client.post("/api/bundles/grabs", json=closed_ref).json()["recorded"] == 0
    with SessionLocal() as db:
        db.get(QuizBank, (SUBJECT, RUN)).open_to_students = True
        db.commit()
    deck = client.get("/api/bundles/decks").json()["decks"][0]
    assert deck["exportId"] and not deck["grabbed"] and deck["filename"] != "legacy.apkg"
    fetched = client.get(BUNDLE, params={"exportId": deck["exportId"]})
    assert fetched.status_code == 200, fetched.text
    notes, models, media, count = contents(fetched.content)
    fixture_dir = os.environ.get("STUDYEZ_ANKI_FIXTURE_DIR")
    if fixture_dir:
        Path(fixture_dir).mkdir(parents=True, exist_ok=True)
        (Path(fixture_dir) / "first.apkg").write_bytes(fetched.content)
    assert len(notes) == count == 8 and len(media) == 1
    assert all("HELD_OUT_EXAM_SENTINEL" not in fields for _, fields in notes)
    assert len(models) == 1 and all("<script>" not in fields for _, fields in notes)
    front, back, meta = notes[1][1].split("\x1f")
    assert "비밀하나" not in front and "비밀둘" not in front and "[ 1 ]" in front
    assert "비밀하나" in back and "비밀둘" in back
    assert "보기둘" in notes[4][1] and "정답 보기" in notes[4][1]
    assert "결과1" in notes[6][1] and "→" in notes[6][1]
    matching_front = notes[6][1].split("\x1f")[0]
    assert "L1:" not in matching_front and "R1:" not in matching_front
    assert "단계1 → 단계2 → 단계3" in notes[7][1]
    assert all(word in notes[0][1] for word in ("충돌 이유", "검토 메모", "대안 답", "외부 의학지식", 'src="bank_'))
    with SessionLocal() as db:
        assert db.query(AssetGrab).count() == 1 and db.query(BankState).count() == 0
    with patch("app.storage.ObjectStorage.upload_fileobj", side_effect=AssertionError("cache must be reused")):
        signed = client.get(URL)
        assert signed.status_code == 200, signed.text
        assert client.get(signed.json()["url"]).content == fetched.content
    assert client.get("/api/bundles/decks").json()["decks"][0]["grabbed"]
    with SessionLocal() as db:
        assert db.query(BankState).count() == 0, "export must not change web study progress"
        row = db.get(QuizBank, (SUBJECT, RUN))
        updated = copy.deepcopy(row.bank)
        updated["questions"][0]["answer"] = "訂正した答"
        row.bank = updated
        row.build_id = "build2"
        db.commit()
    new = client.get("/api/bundles/decks").json()["decks"][0]
    assert not new["grabbed"] and new["exportId"] != deck["exportId"]
    assert client.get(BUNDLE, params={"exportId": deck["exportId"]}).status_code == 409
    body = {"decks": [{"subject": SUBJECT, "runId": RUN, "kind": "main", "exportId": deck["exportId"]}]}
    assert client.post("/api/bundles/grabs", json=body).json()["recorded"] == 0
    revised = client.get(BUNDLE, params={"exportId": new["exportId"]})
    newer, _, _, _ = contents(revised.content)
    assert [n[0] for n in notes] == [n[0] for n in newer], "answer corrections must keep GUIDs"
    assert "訂正した答" in newer[0][1]
    body["decks"][0]["exportId"] = new["exportId"]
    assert client.post("/api/bundles/grabs", json=body).json()["recorded"] == 1
    assert client.get("/api/bundles/decks").json()["decks"][0]["grabbed"]
    with SessionLocal() as db:
        row = db.get(QuizBank, (SUBJECT, RUN))
        row.pages = {"Q1": [2]}
        db.commit()
    assert client.get(URL).status_code == 409, "missing image must not produce an incomplete export"
    with SessionLocal() as db:
        row = db.get(QuizBank, (SUBJECT, RUN))
        row.validation = {"pass": False}
        db.commit()
    assert client.get(URL).status_code == 409
    app.dependency_overrides.clear()
    with SessionLocal() as db:
        row = db.get(QuizBank, (SUBJECT, RUN))
        row.validation = {"pass": True}
        row.pages = {}
        row.open_to_students = False
        db.commit()
    assert client.get(URL, headers=ADMIN).status_code == 200, "admin may preview a closed bank"
    # A second real export is used by the browser bundler verification.
    if fixture_dir:
        second_run = "261007_02"
        with SessionLocal() as db:
            db.add(Lecture(subject=SUBJECT, run_id=second_run, uid="anki-test-2", date=date(2026, 10, 7),
                           slot=2, slot_end=2, start_time="10:00", title="두 번째 강의", professors=[], author="", version=1))
            db.add(QuizBank(subject=SUBJECT, run_id=second_run, bank=bank, validation={"pass": True},
                            build_id="second", pages={"Q1": [1]}, status="ready", open_to_students=True))
            db.add(Asset(id="anki-slide-2", subject=SUBJECT, run_id=second_run, kind="bank_media", slide_no=1,
                         filename="slide.png", object_key="test/slide.png", size_bytes=11))
            db.commit()
        second = client.get(f"/api/bundles/decks/{SUBJECT}/{second_run}/main", headers=ADMIN)
        assert second.status_code == 200, second.text
        (Path(fixture_dir) / "second.apkg").write_bytes(second.content)
    print("PASS: all 8 formats, offline media, escaped content, stable GUIDs, cache, authorization, bundles and revisions")


if __name__ == "__main__":
    main()
