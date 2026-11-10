"""강의록 회독·강의 메모: 본인 것만, 추가·최근 것 지우기·상한, 메모 저장·비우기, 상세·시간표 응답."""

import os
import tempfile
from datetime import date
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="studyez-lecture-notes-"))
os.environ.update(ENVIRONMENT="local-test", DATABASE_URL=f"sqlite:///{(_TMP / 'test.db').as_posix()}")

from fastapi.testclient import TestClient
from app.auth import APP_STUDYEZ, ROLE_MEMBER, CurrentUser, get_current_user
from app.database import Base, SessionLocal, engine
from app.main import app
from app.models import Lecture, LectureMemo, NoteRead, TimetableEvent
from app.routes import lecture_notes

BASE = "/api/lectures/감염학/261103_02"


def main():
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        db.add(TimetableEvent(id="ev1", date=date(2026, 11, 3), start_time="10:00", end_time="10:50",
                              title="감염병의 병인론", category="lecture", course="감염과 면역"))
        db.add(Lecture(subject="감염학", run_id="261103_02", uid="u1", date=date(2026, 11, 3), slot=2, slot_end=2, start_time="10:00", version=1,
                       title="감염병의 병인론", professors=["최은화"], timetable_event_id="ev1"))
        db.commit()
    client = TestClient(app)

    def login(who="student", approved=True):
        app.dependency_overrides[get_current_user] = lambda: CurrentUser(
            id=who, email=f"{who}@example.com", is_admin=False,
            apps={APP_STUDYEZ: ROLE_MEMBER} if approved else {})

    login()
    detail = client.get(BASE).json()
    assert detail["noteReads"] == 0 and detail["myMemo"] == "", detail

    assert client.post(f"{BASE}/note-reads").json() == {"noteReads": 1}
    assert client.post(f"{BASE}/note-reads").json() == {"noteReads": 2}
    assert client.delete(f"{BASE}/note-reads/last").json() == {"noteReads": 1}
    assert client.post(f"{BASE}/note-reads").json() == {"noteReads": 2}  # 되돌리기
    assert client.get(BASE).json()["noteReads"] == 2

    events = client.get("/api/timetable").json()["events"]
    assert events[0]["lectures"][0]["noteReads"] == 2
    quick = client.get("/api/timetable?include_study=false").json()["events"]
    assert quick[0]["lectures"][0]["noteReads"] == 0

    # 메모
    assert client.put(f"{BASE}/my-memo", json={"memo": "슈퍼항원 표 다시\n  "}).json() == {"memo": "슈퍼항원 표 다시"}
    assert client.get(BASE).json()["myMemo"] == "슈퍼항원 표 다시"
    assert client.put(f"{BASE}/my-memo", json={"memo": "x" * (lecture_notes.MAX_MEMO + 1)}).status_code == 422

    # 계정 격리
    login("other")
    other = client.get(BASE).json()
    assert other["noteReads"] == 0 and other["myMemo"] == ""
    assert client.delete(f"{BASE}/note-reads/last").json() == {"noteReads": 0}
    assert client.get("/api/timetable").json()["events"][0]["lectures"][0]["noteReads"] == 0
    login()
    assert client.get(BASE).json()["noteReads"] == 2

    # 비우면 지운다
    assert client.put(f"{BASE}/my-memo", json={"memo": "   "}).json() == {"memo": ""}
    with SessionLocal() as db:
        assert db.query(LectureMemo).count() == 0

    # 상한
    lecture_notes.MAX_READS = 3
    assert client.post(f"{BASE}/note-reads").json() == {"noteReads": 3}
    assert client.post(f"{BASE}/note-reads").status_code == 409
    with SessionLocal() as db:
        assert db.query(NoteRead).filter_by(user_id="student").count() == 3

    # 없는 강의·미승인·미로그인
    assert client.post("/api/lectures/감염학/nope/note-reads").status_code == 404
    login(approved=False)
    assert client.post(f"{BASE}/note-reads").status_code == 403
    assert client.put(f"{BASE}/my-memo", json={"memo": "a"}).status_code == 403
    app.dependency_overrides.clear()
    assert client.post(f"{BASE}/note-reads").status_code == 401
    print("PASS lecture notes")


if __name__ == "__main__":
    main()
