"""Reference slides follow the served question and the disclosure boundary."""
from datetime import date
from unittest.mock import patch

from tests.test_learning import learning_bank, USER
from fastapi.testclient import TestClient
from app.auth import CurrentUser, get_current_user
from app.database import Base, SessionLocal, engine
from app.main import app
from app.models import Asset, Lecture, QuizBank
from app.models.learning import LearningSession
from app.learning_media import references
from app.storage import StorageNotConfigured


def main():
    bank = learning_bank()
    for q in bank["questions"]:
        q["source_refs"] = [{"source_id": "S1", "locator": "p2, p4"}, {"source_id": "S2", "locator": "p99"}]
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        for run in ("lecture", "other"):
            db.add(Lecture(subject="course", run_id=run, uid=run, slot=1, slot_end=1,
                           start_time="09:00", title=run, date=date(2026, 10, 1)))
        db.flush()
        db.add(QuizBank(subject="course", run_id="lecture", build_id="media-v1", bank=bank,
                       pages={q["question_id"]: [7] for q in bank["questions"]},
                       validation={"pass": True}, open_to_students=True))
        for ident, run, kind, page in (("slide2", "lecture", "bank_media", 2),
                                      ("notbank4", "lecture", "main_media", 4),
                                      ("other4", "other", "bank_media", 4),
                                      ("s2", "lecture", "bank_media", 99),
                                      ("fallback7", "lecture", "bank_media", 7),
                                      ("notes", "lecture", "notes_current", None)):
            db.add(Asset(id=ident, subject="course", run_id=run, kind=kind,
                         filename="lecture.pdf" if page is None else f"{page}.png",
                         object_key=ident, content_type="application/pdf" if page is None else "image/png", slide_no=page))
        db.commit()
    app.dependency_overrides[get_current_user] = lambda: USER
    client = TestClient(app)
    def get(path):
        r = client.get("/api/learning" + path); assert r.status_code == 200, r.text
        return r.json()
    def post(path, body=None):
        r = client.post("/api/learning" + path, json=body or {}); assert r.status_code == 200, r.text
        return r.json()
    signed = []
    def sign(key, **kwargs):
        signed.append((key, kwargs))
        return f"https://storage.example/{key}?signature={len(signed)}"
    with patch("app.learning_media.ObjectStorage") as storage:
        storage.return_value.presign_download.side_effect = sign
        sid = post("/sessions", {"mode": "extra", "subject": "course", "runId": "lecture", "count": 1})["sessionId"]
        first = get(f"/sessions/{sid}")
        assert first["feedback"] is None and not signed
        correct = next(o["id"] for o in first["question"]["options"] if o["text"] == "관계 A")
        shown = post(f"/sessions/{sid}/submit", {"token": first["token"], "answer": {"selected": [correct]}, "activeSeconds": 17})
        media = shown["feedback"]
        assert media["correct"] and [s["page"] for s in media["slides"]] == [2]
        assert media["missingSlidePages"] == [4] and media["sourceDocument"]["filename"] == "lecture.pdf"
        assert {key for key, _ in signed} == {"slide2", "notes"}
        assert next(kwargs for key, kwargs in signed if key == "notes")["inline"]
        refreshed = get(f"/sessions/{sid}")
        assert refreshed["feedback"]["slides"][0]["url"] != media["slides"][0]["url"]
        with SessionLocal() as db:
            data = db.get(LearningSession, sid).data
            unit = data["units"][data["entries"][0]["key"]]
            fallback = references(db, unit, {"question_id": "U0-learning", "source_refs": []})
            assert [s["page"] for s in fallback["slides"]] == [7]
            with patch("app.learning_media.ObjectStorage", side_effect=StorageNotConfigured("test")):
                unavailable = references(db, unit, bank["questions"][0])
                assert unavailable["slides"] == [] and unavailable["missingSlidePages"] == [2, 4]
        post(f"/sessions/{sid}/acknowledge", {"token": first["token"], "reviewRating": "Good", "activeSeconds": 19})
        # Exam feedback and its signed source images stay withheld until completion.
        exam = post("/sessions", {"mode": "exam", "subject": "course", "runId": "lecture", "count": 1})["sessionId"]
        before = len(signed)
        attempt = get(f"/sessions/{exam}")
        correct = next(o["id"] for o in attempt["question"]["options"] if o["text"] == "관계 A")
        held = post(f"/sessions/{exam}/submit", {"token": attempt["token"], "answer": {"selected": [correct]}})
        assert held["feedback"] is None and len(signed) == before
        done = post(f"/sessions/{exam}/acknowledge", {"token": attempt["token"]})
        assert done["results"][0]["slides"][0]["page"] == 2
        # Replacing a bank cannot attach newer slides to a frozen old question.
        with SessionLocal() as db:
            row = db.get(QuizBank, ("course", "lecture"))
            row.build_id = "media-v2"; db.commit()
        before = len(signed)
        old = get(f"/sessions/{sid}")
        assert old["status"] == "complete"  # Completed normal sessions do not re-expose answers.
        with SessionLocal() as db:
            old_media = references(db, unit, bank["questions"][0])
            assert old_media["slides"] == [] and old_media["slideStatus"] and len(signed) == before
            row = db.get(QuizBank, ("course", "lecture")); row.open_to_students = False; db.commit()
        assert client.get(f"/api/learning/sessions/{exam}").status_code == 404
        assert len(signed) == before
        # Other users cannot sign another student's frozen session references.
        app.dependency_overrides[get_current_user] = lambda: CurrentUser(
            id="other-user", email="other@example.com", is_admin=False, apps=USER.apps)
        assert client.get(f"/api/learning/sessions/{exam}").status_code == 404
    app.dependency_overrides.clear()
    print("PASS exact S1 pages, asset kind/scope, PDF, fresh signatures, missing storage, legacy page fallback, exam withholding, old builds and authorization")


if __name__ == "__main__": main()
