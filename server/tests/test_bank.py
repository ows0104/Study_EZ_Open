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
import copy  # noqa: E402
import sys  # noqa: E402
from unittest.mock import patch  # noqa: E402

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
            # 걸려서 뺀 문항이 하나 있었던 은행이다(`quizbank.validate.validate_dropping`).
            "validation": {"pass": True, "errors": [], "warnings": [],
                           "dropped": [{"question_id": "Q9", "errors": ["Q9: matching 참조 오류"],
                                        "question": {"question_id": "Q9"}}]},
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
    conversation = "https://chatgpt.com/c/test-bank"
    client.put(f"{ADMIN}/bank-response", json={"raw": RAW, "conversationUrl": conversation}, headers=ADMIN_H)
    responded = client.get(f"{ADMIN}/bank", headers=ADMIN_H).json()["summary"]["respondedAt"]
    revision = {"validation": {"pass": False, "errors": ["Q1: leak"]}}
    failure = client.put(f"{ADMIN}/bank", json={"respondedAt": responded, "message": "응답 수정 필요",
                                              "revision": revision}, headers=RUNNER)
    check("검수 실패 상세를 저장한다", failure.status_code == 200)
    failed_summary = client.get(BASE, headers=ADMIN_H).json()["bank"]
    check("생성 대화와 검수 상세가 관리자에게 연결된다",
          failed_summary["conversationUrl"] == conversation and failed_summary["revision"] == revision)
    with SessionLocal() as db:
        check("다시 넣어도 열린 일감은 하나", db.query(PrequizJob).filter_by(kind="bank").count() == 1)

    detail = client.get(BASE, headers=ADMIN_H).json()
    check("관리자 상세에 자료 순서가 S1 필기 · S2 족보",
          [(s["id"], s["kind"]) for s in detail.get("bankSources", [])] == [("S1", "notes_current"), ("S2", "jokbo")],
          detail.get("bankSources"))
    check("족보는 text/markdown 으로", detail["bankSources"][1]["contentType"] == "text/markdown")
    check("예습 첨부 목록에도 올해 강의 족보와 MIME 형식이 온다",
          any(f["id"] == "a-jokbo" and f["contentType"] == "text/markdown" for f in detail["files"]))
    check("프롬프트용 시험일", detail.get("bankExamDate") == "2026-10-20", detail.get("bankExamDate"))

    print("② 러너")
    got = client.get(f"{ADMIN}/bank-response", headers=RUNNER).json()
    check("원문과 자료를 준다", got["raw"] == RAW and [s["id"] for s in got["sources"]] == ["S1", "S2"])
    stale = client.put(f"{ADMIN}/bank", json=result("2020-01-01T00:00:00+00:00"), headers=RUNNER)
    check("옛 응답의 정리는 409", stale.status_code == 409, stale.status_code)
    # 프롬프트 v1.2 꼴의 합친 충돌 문항 — Q1 이 강의자료·족보 충돌을 외부 의학지식으로 정했다.
    merged = example_bank()
    merged["source_conflicts"] = [{"conflict_id": "CF-1", "description": "강의자료는 A, 족보는 B — 교과서대로 A",
                                   "source_refs": [{"source_id": "S1", "locator": "p1"}], "unresolved": False}]
    merged["questions"][0]["conflict_id"] = "CF-1"
    merged["questions"][0]["source_refs"].append({"source_id": "EXT", "locator": "외부 의학지식"})
    ok = client.put(f"{ADMIN}/bank", json=result(got["respondedAt"], merged), headers=RUNNER)
    check("결과를 받고 ready", ok.status_code == 200 and ok.json()["status"] == "ready", ok.text)
    build1 = ok.json()["buildId"]
    dropped = client.get(f"{ADMIN}/bank", headers=ADMIN_H).json()["summary"]["dropped"]
    check("관리자는 뺀 문항과 이유를 본다", dropped == [{"questionId": "Q9", "errors": ["Q9: matching 참조 오류"]}],
          dropped)

    print("③ 열기")
    as_student()
    check("검증을 통과한 업로드는 학생에게 자동 공개", client.get(f"{BASE}/bank").status_code == 200)
    as_admin()
    check("관리자는 자동 공개된 은행을 닫을 수 있다",
          client.put(f"{ADMIN}/bank/open", json={"open": False}, headers=ADMIN_H).json()["open"] is False)
    as_student()
    check("열기 전 학생에게는 없다", client.get(f"{BASE}/bank").status_code == 404)
    check("상세에도 안 실린다", client.get(BASE).json()["bank"] is None)
    check("학생은 자료 목록을 못 본다", "bankSources" not in client.get(BASE).json())
    check("학생도 개인 예습에 족보를 첨부할 수 있다",
          any(f["id"] == "a-jokbo" for f in client.get(BASE).json()["files"]))
    as_admin()
    check("열린다", client.put(f"{ADMIN}/bank/open", json={"open": True}, headers=ADMIN_H).json()["open"] is True)
    as_student()
    summary = client.get(f"{BASE}/bank").json()
    check("학생에게 생성 대화·검수 상세를 노출하지 않는다",
          "conversationUrl" not in summary["summary"] and "revision" not in summary["summary"])
    check("학생 요약", summary["summary"]["questionCount"] == 3 and "reviewCounts" not in summary["summary"]
          and "dropped" not in summary["summary"],
          summary["summary"])
    check("보기 전 패널 진행 0/3", summary["summary"]["studyQuestionCount"] == 3
          and summary["summary"]["seenQuestionCount"] == 0)
    check("시험일은 같은 과목의 시험", summary["examDate"] == "2026-10-20", summary["examDate"])

    print("④ 풀기")
    start = client.post(f"{BASE}/bank/session/start", json={"size": 10})
    check("회차가 열린다", start.status_code == 200 and start.json()["size"] == 10, start.text)
    first = client.post(f"{BASE}/bank/next").json()
    q = first["question"]
    check("문제를 읽는 동안 이미지 미리 받기", [s["page"] for s in first["preloadSlides"]] == [1])
    check("미리 받기는 답을 펼치지 않는다", first["answer"] is None)
    with SessionLocal() as db:
        served = db.get(BankState, ("student-1", SUBJECT, RUN)).state["served"]
        check("미리 받아도 정답 열람 시각을 기록하지 않는다",
              not served["revealed"] and "revealed_at" not in served)
    check("답 칸이 없다", q and not any(k in q for k in ("answer", "answer_units", "correct_option_ids",
                                                         "answer_pairs", "correct_order")), q)
    again = client.post(f"{BASE}/bank/next").json()
    check("새로고침해도 같은 문항", again["reviewToken"] == first["reviewToken"])
    progress = client.get(BASE).json()["bank"]
    check("강의 패널은 고유 문항 열람 1/3", progress["studyQuestionCount"] == 3
          and progress["seenQuestionCount"] == 1, progress)
    early = client.post(f"{BASE}/bank/rate", json={"reviewToken": first["reviewToken"], "rating": "Good"})
    check("답을 보기 전 평가는 409", early.status_code == 409)
    shown = client.post(f"{BASE}/bank/reveal", json={"reviewToken": first["reviewToken"]}).json()
    check("답이 나온다", shown["answer"] == "예시 정답" and shown["answerUnits"] == ["예시 정답"])
    check("충돌 설명과 자료 밖 표시가 답과 같이 온다",
          shown["conflict"] == "강의자료는 A, 족보는 B — 교과서대로 A" and shown["external"] is True, shown)
    # 예시 은행에서 처음 나갈 수 있는 것은 Q1(direct·Core)뿐이다 — Q2 는 Core 숙련도, Q3 는 선행에 막힌다.
    # 조건문으로 감싸면 다른 문항이 나왔을 때 아래 둘이 조용히 안 돈다.
    check("처음 문항은 Q1", q["question_id"] == "Q1", q["question_id"])
    check("⑤ 외부지식 검토가 같이 온다", (shown["medicalReview"] or {}).get("verdict") == "wrong")
    check("⑤ 인용 쪽 중 올라간 것만 슬라이드로", [s["page"] for s in shown["slides"]] == [1], shown["slides"])
    with SessionLocal() as db:
        before_rating = copy.deepcopy(db.get(BankState, ("student-1", SUBJECT, RUN)).state)
    rate = client.post(f"{BASE}/bank/rate", json={"reviewToken": first["reviewToken"], "rating": "Good"})
    check("평가가 들어간다", rate.status_code == 200 and rate.json()["session"]["reviewed"] == 1, rate.text)
    twice = client.post(f"{BASE}/bank/rate", json={"reviewToken": first["reviewToken"], "rating": "Good"})
    check("두 번은 안 된다", twice.status_code == 409)
    nxt = client.post(f"{BASE}/bank/next").json()
    check("다음 문항은 다른 것", nxt["question"] is None or nxt["question"]["question_id"] != q["question_id"], nxt)
    check("평가 후 되돌리기 토큰 제공", nxt["undoToken"] == first["reviewToken"])
    check("잘못된 되돌리기 토큰 거절", client.post(f"{BASE}/bank/undo", json={"reviewToken": "wrong"}).status_code == 409)
    other = CurrentUser(id="student-2", email="other@example.com", is_admin=False, apps=dict.fromkeys(APP_POLICY, ROLE_ADMIN))
    app.dependency_overrides[get_current_user] = lambda: other
    check("다른 사람의 평가는 되돌리지 못한다", client.post(f"{BASE}/bank/undo", json={"reviewToken": first["reviewToken"]}).status_code == 409)
    as_student()
    undone = client.post(f"{BASE}/bank/undo", json={"reviewToken": first["reviewToken"]})
    restored = undone.json()
    check("이전 문제와 답 복원", undone.status_code == 200 and restored["question"]["question_id"] == q["question_id"]
          and restored["answer"]["answer"] == shown["answer"] and restored["session"]["reviewed"] == 0, restored)
    with SessionLocal() as db:
        after_undo = copy.deepcopy(db.get(BankState, ("student-1", SUBJECT, RUN)).state)
        after_undo["served"]["token"] = before_rating["served"]["token"]
        before_rating["seen_question_ids"] = after_undo["seen_question_ids"]
        check("숙련도·일정·이력·보충·회차 전체 원상복구", after_undo == before_rating)
    check("중복 되돌리기 거절", client.post(f"{BASE}/bank/undo", json={"reviewToken": first["reviewToken"]}).status_code == 409)
    check("예전 문항 토큰 무효", client.post(f"{BASE}/bank/rate", json={"reviewToken": first["reviewToken"], "rating": "Easy"}).status_code == 409)
    check("새로고침 시 복원한 문항 유지", client.post(f"{BASE}/bank/next").json()["reviewToken"] == restored["reviewToken"])
    check("평가 되돌리기도 본 문항 수는 유지", client.get(BASE).json()["bank"]["seenQuestionCount"] == 2)
    client.post(f"{BASE}/bank/rate", json={"reviewToken": restored["reviewToken"], "rating": "Good"})
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

    print("⑧ 개수 제한 없는 학습과 선택한 상한")
    current = client.get(f"{BASE}/bank").json()["session"]
    check("next로 바로 시작해도 제한 없음", current["size"] is None)
    client.post(f"{BASE}/bank/session/end", json={"sessionId": current["session_id"]})
    for payload, count, status in (({}, 31, "active"), ({"size": 10}, 10, "complete")):
        opened = client.post(f"{BASE}/bank/session/start", json={**payload, "continueAfterGoal": True}).json()
        check("선택한 경우에만 상한 저장", opened["size"] == payload.get("size"))
        # 출제 정책과 독립적으로 실제 next/reveal/rate 경로의 종료 조건을 검증한다.
        picked = {"question": example_bank()["questions"][0], "days": 14, "ranked": []}
        with patch("app.routes.bank.engine.select_question", return_value=picked):
            for _ in range(count):
                next_item = client.post(f"{BASE}/bank/next").json()
                token = next_item["reviewToken"]
                client.post(f"{BASE}/bank/reveal", json={"reviewToken": token})
                rated = client.post(f"{BASE}/bank/rate", json={"reviewToken": token, "rating": "Good"})
                assert rated.status_code == 200, rated.text
        session = rated.json()["session"]
        check(f"{count}문항 뒤 상태 {status}", session["reviewed"] == count and session["status"] == status)
        ended = client.post(f"{BASE}/bank/session/end", json={"sessionId": opened["session_id"]}).json()
        check("종료 요약에 풀이 수 보존", ended["status"] == "complete" and ended["reviewed"] == count)
        undo_token = client.get(f"{BASE}/bank").json()["undoToken"]
        reopened = client.post(f"{BASE}/bank/undo", json={"reviewToken": undo_token}).json()
        check("완료 회차 되돌리기 시 재개", reopened["session"]["status"] == "active"
              and reopened["session"]["reviewed"] == count - 1 and reopened["answer"] is not None)
        reread = client.get(f"{BASE}/bank").json()
        check("완료 기록 제거와 회차별 집계 복원", not any(
            s["session_id"] == opened["session_id"] for s in reread["previousSessions"])
              and reread["session"]["ratings"]["Good"] == count - 1)
        client.post(f"{BASE}/bank/session/end", json={"sessionId": opened["session_id"]})
    client.post(f"{BASE}/bank/session/start", json={"size": None, "continueAfterGoal": True})
    check("새 회차는 이전 회차를 되돌리지 못한다", client.post(
        f"{BASE}/bank/undo", json={"reviewToken": undo_token}).status_code == 409)
    with patch("app.routes.bank.engine.select_question", return_value={
            "question": None, "days": 14, "reason": "waiting", "retry_at": None}):
        exhausted = client.post(f"{BASE}/bank/next").json()
    check("제한 없어도 출제할 문항이 없으면 종료", exhausted["question"] is None
          and exhausted["summary"]["reason"] == "no_eligible_question")

    print("9. Every individual daily question must be evaluated")
    from app import study_engine as study
    for rating in ("Again", "Hard", "Good", "Easy"):
        with SessionLocal() as db:
            saved = db.get(BankState, (STUDENT.id, SUBJECT, RUN))
            saved.state = study.empty_state()
            db.commit()
        client.post(f"{BASE}/bank/session/start", json={})
        seen = set()
        for i in range(3):
            first = client.post(f"{BASE}/bank/next").json()
            check("Pending questions remain before completion", first["lectureGoal"]["remaining"] == 3 - i)
            qid = first["question"]["question_id"]
            check("Daily study does not repeat completed questions", qid not in seen)
            seen.add(qid)
            check("New questions increment calendar count immediately", client.get(BASE).json()["bank"]["seenQuestionCount"] == i + 1)
            token = first["reviewToken"]
            client.post(f"{BASE}/bank/reveal", json={"reviewToken": token})
            client.post(f"{BASE}/bank/rate", json={"reviewToken": token, "rating": rating})
        done = client.post(f"{BASE}/bank/next").json()
        check(f"{rating}: completion after all questions", done.get("reason") == "lecture_goal_met"
              and done["lectureGoal"]["met"] and not done.get("waiting")
              and done["summary"]["status"] == "complete", done)
        restored = client.post(f"{BASE}/bank/undo", json={"reviewToken": token}).json()
        check(f"{rating}: undo restores one daily question", restored["lectureGoal"]["remaining"] == 1
              and restored.get("answer") is not None, restored)

    print("10. Extra study preserves daily completion and distinct view counts")
    client.post(f"{BASE}/bank/rate", json={"reviewToken": restored["reviewToken"], "rating": "Good"})
    client.post(f"{BASE}/bank/next")
    for question in example_bank()["questions"]:
        before = client.get(BASE).json()["bank"]["seenQuestionCount"]
        client.post(f"{BASE}/bank/session/start", json={"continueAfterGoal": True})
        picked = {"question": question, "days": 14, "ranked": []}
        with patch("app.routes.bank.engine.select_question", return_value=picked):
            extra = client.post(f"{BASE}/bank/next").json()
        check("Extra study preserves completion", extra["lectureGoal"]["met"])
        repeated = client.post(f"{BASE}/bank/next").json()
        check("Previously viewed questions do not increment distinct count", repeated["reviewToken"] == extra["reviewToken"]
              and client.get(BASE).json()["bank"]["seenQuestionCount"] == before)
        client.post(f"{BASE}/bank/reveal", json={"reviewToken": extra["reviewToken"]})
        client.post(f"{BASE}/bank/rate", json={"reviewToken": extra["reviewToken"], "rating": "Good"})
        client.post(f"{BASE}/bank/session/end", json={"sessionId": extra["session"]["session_id"]})

    print("11. Ordinary study includes unseen variants and advanced questions")
    from app.models import QuizBank
    with SessionLocal() as db:
        bank = example_bank()
        bank["questions"].append({**copy.deepcopy(bank["questions"][0]), "question_id": "Q1-variant"})
        db.get(QuizBank, (SUBJECT, RUN)).bank = bank
        saved = db.get(BankState, (STUDENT.id, SUBJECT, RUN))
        saved.state = study.record_review(bank, study.empty_state(), "Q1", "Again", study.now_ms())
        db.commit()
    client.post(f"{BASE}/bank/session/start", json={})
    for qid, count in (("Q1-variant", 2), ("Q2", 3), ("Q3", 4)):
        extra = client.post(f"{BASE}/bank/next").json()
        check("Unseen ordinary question: " + qid, extra["question"]["question_id"] == qid, extra)
        check("Each unseen question updates panel count", client.get(BASE).json()["bank"]["seenQuestionCount"] == count)
        repeated = client.post(f"{BASE}/bank/next").json()
        check("Refresh preserves current question", repeated["reviewToken"] == extra["reviewToken"])
        client.post(f"{BASE}/bank/reveal", json={"reviewToken": extra["reviewToken"]})
        client.post(f"{BASE}/bank/rate", json={"reviewToken": extra["reviewToken"], "rating": "Again"})
        check("No premature completion with unseen questions", client.get(f"{BASE}/bank").json()["lectureGoal"]["met"] == (count == 4))
    done = client.post(f"{BASE}/bank/next").json()
    check("Ordinary study completes with all variants evaluated", done["question"] is None and done["lectureGoal"]["met"])
    client.post(f"{BASE}/bank/session/start", json={"continueAfterGoal": True})
    extra = client.post(f"{BASE}/bank/next").json()
    check("Real extra study can continue after full daily coverage", extra["question"] is not None and extra["lectureGoal"]["met"])

    print("12. Daily goal includes all unseen questions without a ten-question cap")
    with SessionLocal() as db:
        bank = example_bank()
        bank["questions"] = [{**copy.deepcopy(bank["questions"][0]), "question_id": f"NEW-{i:02d}"}
                             for i in range(15)]
        db.get(QuizBank, (SUBJECT, RUN)).bank = bank
        db.get(BankState, (STUDENT.id, SUBJECT, RUN)).state = study.empty_state()
        db.commit()
    client.post(f"{BASE}/bank/session/start", json={})
    viewed = set()
    for i in range(15):
        picked = client.post(f"{BASE}/bank/next").json()
        check("All unseen questions remain in the daily goal", picked["lectureGoal"]["total"] == 15
              and picked["lectureGoal"]["newRemaining"] == 15 - i)
        qid = picked["question"]["question_id"]
        check("Every new question is distinct", qid not in viewed)
        viewed.add(qid)
        token = picked["reviewToken"]
        client.post(f"{BASE}/bank/reveal", json={"reviewToken": token})
        client.post(f"{BASE}/bank/rate", json={"reviewToken": token, "rating": "Again"})
    done = client.post(f"{BASE}/bank/next").json()
    check("Daily session ends after every unseen question is evaluated", done["question"] is None
          and done["lectureGoal"]["met"] and done["lectureGoal"]["unlearnedRemaining"] == 0)
    restored = client.post(f"{BASE}/bank/undo", json={"reviewToken": done["undoToken"]}).json()
    check("Undo restores one new task beyond the former cap", restored["lectureGoal"]["remaining"] == 1
          and restored["lectureGoal"]["total"] == 15 and not restored["lectureGoal"]["met"])
    client.post(f"{BASE}/bank/rate", json={"reviewToken": restored["reviewToken"], "rating": "Again"})
    client.post(f"{BASE}/bank/next")
    client.post(f"{BASE}/bank/session/start", json={"continueAfterGoal": True})
    extra = client.post(f"{BASE}/bank/next").json()
    check("Extra study reviews known questions after full coverage", extra["question"]["question_id"] in viewed)
    check("Extra review preserves distinct calendar count", client.get(BASE).json()["bank"]["seenQuestionCount"] == 15)
    client.post(f"{BASE}/bank/reveal", json={"reviewToken": extra["reviewToken"]})
    client.post(f"{BASE}/bank/rate", json={"reviewToken": extra["reviewToken"], "rating": "Again"})
    goal = client.get(f"{BASE}/bank").json()["lectureGoal"]
    check("Extra study keeps the same completed daily goal", goal["met"] and goal["total"] == goal["completed"] == 15
          and goal["unlearnedRemaining"] == 0 and goal["reviewedToday"] == 16)


if __name__ == "__main__":
    main()
    print()
    print(f"{'FAIL' if failures else 'OK'} — 실패 {len(failures)}")
    sys.exit(1 if failures else 0)
