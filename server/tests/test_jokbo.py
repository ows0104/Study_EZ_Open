"""족보 풀이(routes/jokbo.py): 러너 업로드 계약 검사, 그림 확인, 관리자 먼저 공개, 학생 읽기·서명 그림."""

import copy
import os
import tempfile
from datetime import date
from pathlib import Path

TMP = Path(tempfile.mkdtemp(prefix="studyez-jokbo-"))
os.environ.update(ENVIRONMENT="local-test", DATABASE_URL=f"sqlite:///{(TMP / 'test.db').as_posix()}",
                  RUNNER_TOKEN="runner-token", STUDYEZ_LOCAL_STORAGE_DIR=str(TMP / "storage"))

from fastapi.testclient import TestClient  # noqa: E402
from app.auth import APP_STUDYEZ, ROLE_MEMBER, CurrentUser, get_current_user  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import TimetableEvent  # noqa: E402

RUNNER = {"Authorization": "Bearer runner-token"}
DOC = {
    "schema": "jokbo-solve/1",
    "lecture": {"eventId": "ev18", "runId": "261109_01", "number": "18", "title": "헤모필루스",
                "currentProfessors": ["갑"], "professorSource": "notes"},
    "sections": [{"kind": "same", "professors": ["갑"], "years": ["2025"], "itemIds": ["a"]},
                 {"kind": "other", "professors": ["을"], "years": ["2020"], "itemIds": ["b"]}],
    "items": [
        {"id": "a", "year": 2025, "number": 1, "stem": "발문", "choices": ["1", "2"], "answers": [1],
         "answerMode": "one_of", "answerStatus": "key", "verification": "pending", "explanation": None,
         "figures": [{"file": "a-1.png", "w": 1, "h": 1}]},
        {"id": "b", "year": 2020, "number": 2, "stem": "발문", "choices": ["1", "2"], "answers": [2],
         "answerMode": "one_of", "answerStatus": "key", "verification": "pending", "explanation": None},
    ],
}


def main():
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        db.add(TimetableEvent(id="ev18", date=date(2026, 11, 9), start_time="09:00", end_time="09:50",
                              title="감염과 면역 18", category="lecture", course="감염과 면역"))
        db.commit()
    client = TestClient(app)

    def login(admin=False):
        app.dependency_overrides[get_current_user] = lambda: CurrentUser(
            id="admin" if admin else "student", email="x@example.com", is_admin=admin,
            apps={APP_STUDYEZ: ROLE_MEMBER})

    # 업로드 전: 없음
    login()
    assert client.get("/api/jokbo/events/ev18/summary").status_code == 404

    # 계약 위반·경로 불일치·없는 칸·그림 없음은 거절
    bad = copy.deepcopy(DOC)
    bad["sections"].reverse()
    assert client.put("/api/admin/jokbo/events/ev18", json=bad, headers=RUNNER).status_code == 422
    assert client.put("/api/admin/jokbo/events/nope", json=DOC, headers=RUNNER).status_code == 404
    r = client.put("/api/admin/jokbo/events/ev18", json=DOC, headers=RUNNER)
    assert r.status_code == 409 and r.json()["detail"]["files"] == ["a-1.png"], r.text

    # 그림 → 문서. 기본은 관리자에게만.
    assert client.get("/api/admin/jokbo/figures/a-1.png", headers=RUNNER).json()["size"] is None
    assert client.put("/api/admin/jokbo/figures/a-1.png", content=b"\x89PNG", headers=RUNNER).json()["size"] == 4
    assert client.put("/api/admin/jokbo/figures/..%2Fx.png", content=b"x", headers=RUNNER).status_code in (404, 422)
    r = client.put("/api/admin/jokbo/events/ev18", json=DOC, headers=RUNNER)
    assert r.status_code == 200 and r.json()["audience"] == "admin" and r.json()["sameItems"] == 1, r.text

    assert client.get("/api/jokbo/events/ev18/summary").status_code == 404  # 학생에게는 아직 안 보인다
    login(admin=True)
    got = client.get("/api/jokbo/events/ev18").json()
    assert got["otherItems"] == 1 and got["doc"]["items"][0]["figures"][0]["url"], got

    # 모두에게 연다
    assert client.put("/api/admin/jokbo/events/ev18?audience=all", json=DOC, headers=RUNNER).status_code == 200
    login()
    s = client.get("/api/jokbo/events/ev18/summary").json()
    assert s == {"eventId": "ev18", "audience": "all", "items": 2, "sameItems": 1, "otherItems": 1, "unknownItems": 0}, s
    assert client.get("/api/jokbo/events/ev18").json()["doc"]["items"][1]["answers"] == [2]

    # 학생은 올릴 수 없다
    assert client.put("/api/admin/jokbo/events/ev18", json=DOC).status_code in (401, 403)
    print("jokbo: 모두 통과")


if __name__ == "__main__":
    main()
