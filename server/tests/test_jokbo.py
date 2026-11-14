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

    # ── 오답노트(2026-11-14)
    assert client.get("/api/jokbo/wrong-notes").json() == {"items": [], "missing": 0}
    ans = lambda item, result: client.post(f"/api/jokbo/events/ev18/items/{item}/answer", json={"result": result})
    mark = lambda item, band: client.put(f"/api/jokbo/events/ev18/items/{item}/mark", json={"band": band})
    assert ans("zz", "wrong").status_code == 404  # 없는 문항
    assert ans("a", "maybe").status_code == 422
    # 맞히면 기록만, 표시는 안 붙는다
    m = ans("a", "correct").json()
    assert m["band"] is None and m["rightCount"] == 1 and m["lastResult"] == "correct", m
    assert client.get("/api/jokbo/wrong-notes").json()["items"] == []
    # 틀리면 「틀림」이 붙고, 다시 맞혀도 떼지 않는다
    assert ans("b", "wrong").json()["band"] == "high"
    m = ans("b", "correct").json()
    assert m["band"] == "high" and m["wrongCount"] == 1 and m["rightCount"] == 1, m
    # 손으로 표시: a를 「헷갈림」
    assert mark("a", "low").json()["band"] == "low"
    assert mark("a", "top").status_code == 422
    notes = client.get("/api/jokbo/wrong-notes").json()
    assert [e["item"]["id"] for e in notes["items"]] == ["b", "a"], notes  # 상 → 하
    first = notes["items"][0]
    assert first["kind"] == "other" and first["professors"] == ["을"] and first["lecture"]["eventId"] == "ev18"
    assert notes["items"][1]["item"]["figures"][0]["url"]
    # 떼면 빠지고, 푼 기록은 남는다
    m = mark("b", None).json()
    assert m["band"] is None and m["wrongCount"] == 1, m
    assert [e["item"]["id"] for e in client.get("/api/jokbo/wrong-notes").json()["items"]] == ["a"]
    assert len(client.get("/api/jokbo/marks?eventId=ev18").json()["marks"]) == 2
    # 족보 회독: 마무리 화면에 닿을 때마다 한 줄. 시간표 칸에 실린다.
    def rounds_on_timetable():
        events = client.get("/api/timetable").json()["events"]
        return next(e["jokboRounds"] for e in events if e["id"] == "ev18")
    assert rounds_on_timetable() == 0
    assert client.post("/api/jokbo/events/ev18/rounds").json() == {"jokboRounds": 1}
    assert client.post("/api/jokbo/events/ev18/rounds").json() == {"jokboRounds": 2}
    assert rounds_on_timetable() == 2
    assert client.post("/api/jokbo/events/nope/rounds").status_code == 404
    assert next(e for e in client.get("/api/timetable?include_study=false").json()["events"]
                if e["id"] == "ev18")["jokboRounds"] == 0
    # 남의 기록은 안 보인다
    login(admin=True)
    assert client.get("/api/jokbo/marks").json()["marks"] == []
    assert rounds_on_timetable() == 0
    # 족보를 관리자 전용으로 되돌리면 학생 오답노트에서는 빠지고 missing으로 센다
    assert client.put("/api/admin/jokbo/events/ev18", json=DOC, headers=RUNNER).status_code == 200
    login()
    assert client.get("/api/jokbo/wrong-notes").json() == {"items": [], "missing": 1}
    assert ans("a", "wrong").status_code == 404
    assert client.post("/api/jokbo/events/ev18/rounds").status_code == 404  # 안 보이는 족보에는 못 더한다
    print("jokbo: 모두 통과")


if __name__ == "__main__":
    main()
