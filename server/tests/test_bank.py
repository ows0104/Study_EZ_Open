"""Quiz Bank 경로 — 넣고, 정리해 올리고, 열고, 푼다.

2026-10-04 에 섰다(`app/routes/bank.py`). 재는 것.

    ① 완료 표시 없는 응답은 안 받는다 · 받으면 일감(kind=bank)이 선다
    ② 러너가 옛 응답의 정리로 새 응답을 덮지 못한다 (respondedAt)
    ③ 학생은 관리자가 연 은행만 본다
    ④ 답은 reveal 전에 안 나가고, 평가는 reveal 뒤 한 번만
    ⑤ reveal 이 인용 쪽 슬라이드와 외부지식 검토를 같이 준다
    ⑥ 은행을 다시 만들면 학생 상태가 새로 시작하고 옛것은 밀려 남는다
    ⑦ 관리자는 신고를 편을 가로질러 문항별로 보고 닫는다 · 옛 빌드의 신고는 갈라 둔다

    server/.venv/Scripts/python.exe -m tests.test_bank
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="studyez-bank-"))
os.environ.update(
    ENVIRONMENT="local-test",
    DATABASE_URL=f"sqlite:///{(_TMP / 'bank.db').as_posix()}",
    STUDYEZ_LOCAL_STORAGE_DIR=str(_TMP / "storage"),
    PUBLIC_API_BASE_URL="http://testserver",
    RUNNER_TOKEN="runner-token",
)

import datetime  # noqa: E402
import sys  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402

from app.auth import APP_POLICY, ROLE_ADMIN, CurrentUser, get_current_user  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Asset, BankState, Lecture, PrequizJob, Profile, TimetableEvent  # noqa: E402
from tests.bank_fixtures import example_bank  # noqa: E402

ADMIN_H = {"Authorization": "Bearer local-test-token"}
RUNNER = {"Authorization": "Bearer runner-token"}
SUBJECT, RUN = "약리학", "261002_02"
BASE = f"/api/lectures/{SUBJECT}/{RUN}"
ADMIN = f"/api/admin/lectures/{SUBJECT}/{RUN}"
RAW = "## 1. Concept Map\n" + "문항 블록 " * 60 + "\nSTUDYEZ_BANK_COMPLETE"

failures: list[str] = []


def check(label: str, condition: bool, detail: object = "") -> None:
    print(f"  {'PASS' if condition else 'FAIL'}  {label}" + (f"  <- {detail}" if not condition else ""))
    if not condition:
        failures.append(label)


STUDENT = CurrentUser(id="student-1", email="s@example.com", is_admin=False,
                      apps=dict.fromkeys(APP_POLICY, ROLE_ADMIN))


def as_student() -> None:
    app.dependency_overrides[get_current_user] = lambda: STUDENT


def as_admin() -> None:
    app.dependency_overrides.pop(get_current_user, None)


def result(respondedAt: str, bank: dict | None = None) -> dict:
    bank = bank or example_bank()
    return {"respondedAt": respondedAt, "bank": bank,
            "validation": {"pass": True, "errors": [], "warnings": []},
            "review": {"summary": "s", "missing": [], "counts": {"ok": 2, "doubt": 0, "wrong": 1},
                       "reviews": [{"question_id": "Q1", "verdict": "wrong", "note": "교과서와 다르다",
                                    "suggested_answer": "고친 답"}]},
            "pages": {"Q1": [1, 2]}, "usage": []}


def main() -> None:
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        db.add(TimetableEvent(id="ev-lec", date=datetime.date(2026, 10, 2), start_time="10:00", end_time="10:50",
                              title="약물의 이해 5", category="lecture", course="약물의 이해"))
        db.add(TimetableEvent(id="ev-other", date=datetime.date(2026, 10, 10), start_time="09:00", end_time="11:00",
                              title="다른 과목 시험", category="exam", course="다른 과목"))
        db.add(TimetableEvent(id="ev-exam", date=datetime.date(2026, 10, 20), start_time="09:00", end_time="11:00",
                              title="약물의 이해 시험", category="exam", course="약물의 이해"))
        db.add(Lecture(subject=SUBJECT, run_id=RUN, uid=f"{RUN}#콜린성", date=datetime.date(2026, 10, 2), slot=2,
                       slot_end=2, start_time="10:00", title="콜린성 약리학(2)", professors=["이철환"], author="",
                       version=1, timetable_event_id="ev-lec"))
        db.add(Asset(id="a-notes", subject=SUBJECT, run_id=RUN, kind="notes_current", filename="필기.pdf",
                     object_key=f"lectures/{SUBJECT}/{RUN}/notes_current/필기.pdf", content_type="application/pdf"))
        db.add(Asset(id="a-jokbo", subject=SUBJECT, run_id=RUN, kind="jokbo", filename="L12-13.md",
                     object_key=f"lectures/{SUBJECT}/{RUN}/jokbo/L12-13.md", content_type="text/markdown"))
        db.add(Asset(id="a-s1", subject=SUBJECT, run_id=RUN, kind="bank_media", filename=f"{RUN}_s001.png",
                     object_key=f"lectures/{SUBJECT}/{RUN}/bank_media/{RUN}_s001.png", slide_no=1))
        db.commit()
    client = TestClient(app)

    print("① 응답 넣기")
    bad = client.put(f"{ADMIN}/bank-response", json={"raw": "짧은 " * 100}, headers=ADMIN_H)
    check("완료 표시가 없으면 422", bad.status_code == 422, bad.status_code)
    put = client.put(f"{ADMIN}/bank-response", json={"raw": RAW, "promptVersion": "1.1"}, headers=ADMIN_H)
    check("응답을 받는다", put.status_code == 200, put.text)
    responded = put.json()["respondedAt"]
    with SessionLocal() as db:
        jobs = db.query(PrequizJob).filter_by(subject=SUBJECT, run_id=RUN, kind="bank").all()
    check("일감이 하나 선다", len(jobs) == 1 and jobs[0].origin == "button", [(j.kind, j.origin) for j in jobs])
    client.put(f"{ADMIN}/bank-response", json={"raw": RAW}, headers=ADMIN_H)
    responded = client.get(f"{ADMIN}/bank", headers=ADMIN_H).json()["summary"]["respondedAt"]
    with SessionLocal() as db:
        check("다시 넣어도 열린 일감은 하나", db.query(PrequizJob).filter_by(kind="bank").count() == 1)

    detail = client.get(BASE, headers=ADMIN_H).json()
    check("관리자 상세에 자료 순서가 S1 필기 · S2 족보",
          [(s["id"], s["kind"]) for s in detail.get("bankSources", [])] == [("S1", "notes_current"), ("S2", "jokbo")],
          detail.get("bankSources"))
    check("족보는 text/markdown 으로", detail["bankSources"][1]["contentType"] == "text/markdown")
    check("프롬프트용 시험일", detail.get("bankExamDate") == "2026-10-20", detail.get("bankExamDate"))

    print("② 러너")
    got = client.get(f"{ADMIN}/bank-response", headers=RUNNER).json()
    check("원문과 자료를 준다", got["raw"] == RAW and [s["id"] for s in got["sources"]] == ["S1", "S2"])
    stale = client.put(f"{ADMIN}/bank", json=result("2020-01-01T00:00:00+00:00"), headers=RUNNER)
    check("옛 응답의 정리는 409", stale.status_code == 409, stale.status_code)
    ok = client.put(f"{ADMIN}/bank", json=result(got["respondedAt"]), headers=RUNNER)
    check("결과를 받고 ready", ok.status_code == 200 and ok.json()["status"] == "ready", ok.text)
    build1 = ok.json()["buildId"]

    print("③ 열기")
    as_student()
    check("열기 전 학생에게는 없다", client.get(f"{BASE}/bank").status_code == 404)
    check("상세에도 안 실린다", client.get(BASE).json()["bank"] is None)
    check("학생은 자료 목록을 못 본다", "bankSources" not in client.get(BASE).json())
    as_admin()
    check("열린다", client.put(f"{ADMIN}/bank/open", json={"open": True}, headers=ADMIN_H).json()["open"] is True)
    as_student()
    summary = client.get(f"{BASE}/bank").json()
    check("학생 요약", summary["summary"]["questionCount"] == 3 and "reviewCounts" not in summary["summary"],
          summary["summary"])
    check("시험일은 같은 과목의 시험", summary["examDate"] == "2026-10-20", summary["examDate"])

    print("④ 풀기")
    start = client.post(f"{BASE}/bank/session/start", json={"size": 10})
    check("회차가 열린다", start.status_code == 200 and start.json()["size"] == 10, start.text)
    first = client.post(f"{BASE}/bank/next").json()
    q = first["question"]
    check("답 칸이 없다", q and not any(k in q for k in ("answer", "answer_units", "correct_option_ids",
                                                         "answer_pairs", "correct_order")), q)
    again = client.post(f"{BASE}/bank/next").json()
    check("새로고침해도 같은 문항", again["reviewToken"] == first["reviewToken"])
    early = client.post(f"{BASE}/bank/rate", json={"reviewToken": first["reviewToken"], "rating": "Good"})
    check("답을 보기 전 평가는 409", early.status_code == 409)
    shown = client.post(f"{BASE}/bank/reveal", json={"reviewToken": first["reviewToken"]}).json()
    check("답이 나온다", shown["answer"] == "예시 정답" and shown["answerUnits"] == ["예시 정답"])
    # 예시 은행에서 처음 나갈 수 있는 것은 Q1(direct·Core)뿐이다 — Q2 는 Core 숙련도, Q3 는 선행에 막힌다.
    # 조건문으로 감싸면 다른 문항이 나왔을 때 아래 둘이 조용히 안 돈다.
    check("처음 문항은 Q1", q["question_id"] == "Q1", q["question_id"])
    check("⑤ 외부지식 검토가 같이 온다", (shown["medicalReview"] or {}).get("verdict") == "wrong")
    check("⑤ 인용 쪽 중 올라간 것만 슬라이드로", [s["page"] for s in shown["slides"]] == [1], shown["slides"])
    rate = client.post(f"{BASE}/bank/rate", json={"reviewToken": first["reviewToken"], "rating": "Good"})
    check("평가가 들어간다", rate.status_code == 200 and rate.json()["session"]["reviewed"] == 1, rate.text)
    twice = client.post(f"{BASE}/bank/rate", json={"reviewToken": first["reviewToken"], "rating": "Good"})
    check("두 번은 안 된다", twice.status_code == 409)
    nxt = client.post(f"{BASE}/bank/next").json()
    check("다음 문항은 다른 것", nxt["question"] is None or nxt["question"]["question_id"] != q["question_id"], nxt)
    fb = client.post(f"{BASE}/bank/feedback", json={"questionId": q["question_id"], "category": "content",
                                                     "comment": "답이 이상하다"})
    check("피드백이 남는다", fb.status_code == 201, fb.text)
    cmap = client.get(f"{BASE}/bank").json()["conceptMap"]
    direct = next(d for d in cmap[0]["directions"] if d["direction"] == "direct")
    check("개념 지도가 이 사람의 숙련도를 싣는다", direct["mastery"] > 0 and direct["reviews"] == 1, cmap)

    print("⑥ 다시 만들기")
    as_admin()
    client.put(f"{ADMIN}/bank-response", json={"raw": RAW + " "}, headers=ADMIN_H)
    fresh = client.get(f"{ADMIN}/bank-response", headers=RUNNER).json()
    build2 = client.put(f"{ADMIN}/bank", json=result(fresh["respondedAt"]), headers=RUNNER).json()["buildId"]
    check("새 빌드 ID", build2 != build1)
    as_student()
    client.post(f"{BASE}/bank/next")
    with SessionLocal() as db:
        state = db.get(BankState, ("student-1", SUBJECT, RUN))
        check("새 은행에서 새로 시작", state.build_id == build2 and state.state["history"] == [])
        check("옛 상태는 밀어 둔다", state.previous and state.previous["build_id"] == build1
              and len(state.previous["state"]["history"]) == 1)
    as_admin()
    admin_view = client.get(f"{ADMIN}/bank", headers=ADMIN_H).json()
    check("관리자는 피드백을 본다", admin_view["feedback"][0]["comment"] == "답이 이상하다")

    print("⑦ 신고 탭 — 편을 가로질러 문항별로")
    # 의존성을 덮어 쓴 학생은 로그인을 안 지나서 profile 이 없다. 운영에서는 로그인이 세운다.
    with SessionLocal() as db:
        db.add(Profile(id=STUDENT.id, email=STUDENT.email))
        db.commit()
    as_student()
    client.post(f"{BASE}/bank/feedback", json={"questionId": q["question_id"], "category": "wording"})
    client.post(f"{BASE}/bank/feedback", json={"questionId": q["question_id"], "category": "good"})
    as_admin()
    board = client.get("/api/admin/bank-feedback", headers=ADMIN_H).json()
    check("같은 문항의 신고는 한 묶음", len(board["questions"]) == 1 and len(board["questions"][0]["reports"]) == 2,
          board)
    group = board["questions"][0]
    check("좋은 문제는 신고가 아니다", all(r["category"] != "good" for r in group["reports"]))
    check("문면이 같이 온다", (group["question"] or {}).get("question_id") == q["question_id"])
    check("누가 신고했나", {r["email"] for r in group["reports"]} == {"s@example.com"}, group["reports"])
    stale = {r["category"]: r["stale"] for r in group["reports"]}
    check("옛 빌드의 신고는 갈라 둔다", stale == {"content": True, "wording": False}, stale)
    check("열린 묶음 하나", board["open"] == 1 and board["done"] == 0)
    ids = [r["id"] for r in group["reports"]]
    done = client.put("/api/admin/bank-feedback", json={"ids": ids, "status": "resolved"}, headers=ADMIN_H)
    check("반영했다로 닫는다", done.status_code == 200 and done.json()["updated"] == 2, done.text)
    board = client.get("/api/admin/bank-feedback", headers=ADMIN_H).json()
    check("닫으면 열린 것 0", board["open"] == 0 and board["done"] == 1)
    missing = client.put("/api/admin/bank-feedback", json={"ids": [*ids, 99999], "status": "open"}, headers=ADMIN_H)
    check("없는 신고가 섞이면 404 · 아무것도 안 바꾼다", missing.status_code == 404
          and client.get("/api/admin/bank-feedback", headers=ADMIN_H).json()["open"] == 0)
    as_student()
    check("학생은 못 본다", client.get("/api/admin/bank-feedback").status_code == 403)


if __name__ == "__main__":
    main()
    print()
    print(f"{'FAIL' if failures else 'OK'} — 실패 {len(failures)}")
    sys.exit(1 if failures else 0)
