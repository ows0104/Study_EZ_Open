"""한 편의 강의가 서버를 통과하는 전 과정.

로컬 러너가 밀어 넣고, 캘린더가 점을 찍고, 사용자가 풀고, "놓친 것"이 남는다.
SQLite로 돈다 — Postgres 고유 기능을 쓰지 않는다는 것도 같이 확인된다.

    server/.venv/Scripts/python.exe -m tests.test_smoke
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="studyez-smoke-"))
os.environ.update(
    ENVIRONMENT="local-test",
    DATABASE_URL=f"sqlite:///{(_TMP / 'smoke.db').as_posix()}",
    STUDYEZ_LOCAL_STORAGE_DIR=str(_TMP / "storage"),
    PUBLIC_API_BASE_URL="http://testserver",
    RUNNER_TOKEN="runner-token",
)

import httpx  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import TimetableEvent  # noqa: E402


USER = {"Authorization": "Bearer local-test-token"}
RUNNER = {"Authorization": "Bearer runner-token"}

failures: list[str] = []


def check(label: str, condition: bool, detail: object = "") -> None:
    print(f"  {'PASS' if condition else 'FAIL'}  {label}" + (f"  <- {detail}" if not condition else ""))
    if not condition:
        failures.append(label)


def main() -> None:
    Base.metadata.create_all(engine)

    from app.database import SessionLocal

    with SessionLocal() as db:
        db.add(
            TimetableEvent(
                id="official-test-1",
                date=__import__("datetime").date(2026, 8, 13),
                start_time="11:00",
                end_time="11:50",
                title="질병의 병리학적 이해 12",
                details="조직 재생 및 수복(2)\n김혜령",
                professor="김혜령",
                category="lecture",
                course="질병의 병리학적 이해",
                slot=3,
            )
        )
        db.commit()

    client = TestClient(app)

    print("\n[1] 강의 등록 — 시간표 칸에 자동으로 붙는가")
    response = client.post(
        "/api/admin/lectures",
        headers=RUNNER,
        json=[
            {
                "subject": "병리학",
                "runId": "260813_03",
                "uid": "260813_03#조직재생및수복#김혜령",
                "date": "2026-08-13",
                "slot": 3,
                "slotEnd": 3,
                "startTime": "11:00",
                "title": "조직 재생 및 수복(2)",
                "professors": ["김혜령"],
                "author": "최나예",
                "version": 1,
            }
        ],
    )
    check("등록 200", response.status_code == 200, response.text)
    check("시간표 칸에 붙었다", response.json().get("linked") == 1, response.json())

    print("\n[2] run_id 단독으로는 못 찾는다 — 키가 (subject, run_id)인가")
    check(
        "다른 과목의 같은 run_id는 404",
        client.get("/api/lectures/감염과면역/260813_03", headers=USER).status_code == 404,
    )

    print("\n[3] 파일 — 서명 URL로 올리고 서명 URL로 받는다")
    files = [
        {"kind": "notes_current", "filename": "노트.pdf", "sizeBytes": 5, "contentType": "application/pdf"},
        {"kind": "media", "filename": "path_s006.png", "sizeBytes": 3, "contentType": "image/png"},
    ]
    presigned = client.post(
        "/api/admin/lectures/병리학/260813_03/uploads", headers=RUNNER, json=files
    ).json()["files"]
    for entry in presigned:
        # 서명 URL은 Authorization 헤더 없이 열린다. 러너가 하는 그대로 흉내 낸다.
        path = httpx.URL(entry["uploadUrl"]).path
        client.put(path, content=b"PDF" if entry["kind"] == "notes_current" else b"PNG")
    completed = client.post(
        "/api/admin/lectures/병리학/260813_03/uploads/complete", headers=RUNNER, json=files
    ).json()
    check("두 파일 다 확인됨", completed == {"stored": 2, "missing": []}, completed)

    print("\n[4] 계약에 없는 종류는 거절한다")
    rejected = client.post(
        "/api/admin/lectures/병리학/260813_03/uploads",
        headers=RUNNER,
        json=[{"kind": "structure_json", "filename": "structure.json"}],
    )
    check("422로 막힌다", rejected.status_code == 422, rejected.text)

    print("\n[5] 예습 링크 — share가 기본, /c/는 설정으로 열고 닫는다")
    client.put(
        "/api/admin/lectures/병리학/260813_03/preview",
        headers=RUNNER,
        json={
            "provider": "chatgpt",
            "shareUrl": "https://chatgpt.com/share/abc",
            "conversationUrl": "https://chatgpt.com/c/secret",
        },
    )
    detail = client.get("/api/lectures/병리학/260813_03", headers=USER).json()
    check("share_url은 언제나 보인다", detail["preview"]["shareUrl"].endswith("/share/abc"), detail["preview"])

    from app.config import get_settings
    from app.models import Preview
    from app.routes.lectures import _preview_payload

    sample = Preview(
        subject="병리학", run_id="260813_03", provider="chatgpt",
        share_url="https://chatgpt.com/share/abc", conversation_url="https://chatgpt.com/c/link",
    )
    check("관리자에게는 지금도 /c/가 간다", "conversationUrl" in _preview_payload(sample, is_admin=True))
    check("일반 사용자에게는 아직 안 간다", "conversationUrl" not in _preview_payload(sample, is_admin=False))

    # `/c/`가 안정되면 설정 하나로 모두에게 연다. 코드를 고치는 일이 아니라는
    # 것이 요점이므로, 그 스위치가 실제로 통하는지 확인해 둔다.
    get_settings.cache_clear()
    os.environ["STUDYEZ_SHOW_CONVERSATION_URL"] = "true"
    try:
        opened = _preview_payload(sample, is_admin=False)
        check("설정을 켜면 모두에게 간다", opened.get("conversationUrl", "").endswith("/c/link"), opened)
    finally:
        os.environ.pop("STUDYEZ_SHOW_CONVERSATION_URL")
        get_settings.cache_clear()

    print("\n[6] Pre-Quiz — 정답이 문제와 함께 나가지 않는가")
    client.put(
        "/api/admin/lectures/병리학/260813_03/pre-items",
        headers=RUNNER,
        json={
            "lecture_id": "260813_03",
            "items": [
                {
                    "id": "p001", "qtype": "mcq",
                    "stem": "다음 중 해당하지 **않는 것은**?",
                    "choices": ["가", "나", "다", "라", "마"],
                    "answer": "3", "focus": "must_know", "slide_no": 6,
                },
                {
                    "id": "p002", "qtype": "short",
                    "stem": "약어로 무엇인가?", "answer": "LHON", "focus": "core",
                    "explanation": "Leber hereditary optic neuropathy / LHON / "
                                   "Leber 유전성 시신경병증 어느 표기든 정답이다.\n뒤이은 해설.",
                },
                {"id": "p003", "qtype": "ox", "stem": "맞는가?", "answer": "O", "focus": "context"},
            ],
        },
    )
    quiz = client.get("/api/lectures/병리학/260813_03/prequiz", headers=USER).json()
    check("문항 3개", len(quiz["items"]) == 3, quiz)
    check("**강조**가 살아 있다", "**않는 것은**" in quiz["items"][0]["stem"], quiz["items"][0]["stem"])
    leaked = sorted({"answer", "explanation"} & {key for item in quiz["items"] for key in item})
    check("answer·explanation 필드가 없다", not leaked, leaked)
    # 필드 이름을 지웠어도 값이 다른 자리에 실리면 마찬가지다.
    check("정답 문자열이 어디에도 없다", "LHON" not in str(quiz), quiz)

    print("\n[7] 채점 — 허용 표기와 근거 슬라이드")
    graded = client.post(
        "/api/lectures/병리학/260813_03/prequiz/grade",
        headers=USER, json={"itemId": "p002", "answered": "leber 유전성 시신경병증"},
    ).json()
    check("별칭 표기도 정답", graded["correct"] is True, graded)

    wrong = client.post(
        "/api/lectures/병리학/260813_03/prequiz/grade",
        headers=USER, json={"itemId": "p001", "answered": "1"},
    ).json()
    check("틀린 답은 오답", wrong["correct"] is False, wrong)
    check("근거 슬라이드가 붙는다", bool(wrong["slideUrl"]), wrong)

    ox = client.post(
        "/api/lectures/병리학/260813_03/prequiz/grade",
        headers=USER, json={"itemId": "p003", "answered": "x"},
    ).json()
    check("OX 오답", ox["correct"] is False, ox)

    print("\n[8] 놓친 것 — must_know가 먼저 오는가")
    detail = client.get("/api/lectures/병리학/260813_03", headers=USER).json()
    missed = detail["prequiz"]["missed"]
    check("두 개를 놓쳤다", len(missed) == 2, missed)
    check("must_know가 맨 앞", missed and missed[0]["itemId"] == "p001", missed)
    check("점수가 남았다", detail["prequiz"]["correct"] == 1, detail["prequiz"])

    print("\n[9] 캘린더 — 시간표 칸에 점이 붙는가")
    timetable = client.get("/api/timetable", headers=USER).json()["events"]
    linked = [event for event in timetable if event["lectures"]]
    check("칸 하나에 강의가 붙었다", len(linked) == 1, timetable)
    marks = linked[0]["lectures"][0]["marks"]
    check("자료·퀴즈·예습 점이 켜졌다", all(marks[key] for key in ("notes", "prequiz", "preview")), marks)

    print("\n[10] 로그인 없이는 아무것도 안 나간다")
    check("401", client.get("/api/timetable").status_code == 401)
    check("러너 토큰 없이 등록 불가", client.post("/api/admin/lectures", json=[]).status_code in (401, 403))

    print("\n[11] 승인 게이트 — 가입만으로는 자료가 안 보인다")
    from app.auth import CurrentUser, require_approved_user
    from fastapi import HTTPException

    pending = CurrentUser(id="u1", email="new@snu.ac.kr", is_admin=False, is_approved=False)
    try:
        require_approved_user(pending)
        check("승인 전에는 막힌다", False, "통과해 버렸다")
    except HTTPException as exc:
        check("403으로 막힌다", exc.status_code == 403, exc.status_code)
        # 프론트가 "승인 대기 중" 화면과 진짜 권한 오류를 갈라야 한다.
        check("pending_approval 코드가 실린다", exc.detail.get("code") == "pending_approval", exc.detail)

    approved = CurrentUser(id="u2", email="ok@snu.ac.kr", is_admin=False, is_approved=True)
    check("승인되면 통과한다", require_approved_user(approved) is approved)

    print("\n[12] R2가 없어도 서버는 돈다 — 파일 경로만 잠긴다")
    # 첫 배포는 R2 없이 나간다. 캘린더가 시간표만으로 완성되는 화면이라
    # 저장소를 필수로 걸면 쓸 수 있는 것까지 못 올리게 된다.
    from app.config import get_settings as _settings
    from app.routes.common import storage_or_503
    from fastapi import HTTPException as _HTTPException

    _settings.cache_clear()
    saved = os.environ["ENVIRONMENT"]
    # production에서는 SUPABASE_URL이 필수라 같이 채워 준다. 여기서 보려는 것은
    # R2가 비었을 때의 동작이지 그쪽이 아니다.
    os.environ["ENVIRONMENT"] = "production"
    os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
    try:
        check("R2 없으면 storage_configured가 False", _settings().storage_configured is False)
        try:
            storage_or_503()
            check("파일 경로가 막힌다", False, "통과해 버렸다")
        except _HTTPException as exc:
            check("503으로 답한다", exc.status_code == 503, exc.status_code)
            check(
                "storage_unconfigured 코드",
                exc.detail.get("code") == "storage_unconfigured",
                exc.detail,
            )
    finally:
        os.environ["ENVIRONMENT"] = saved
        _settings.cache_clear()

    # 캘린더는 그대로 돌아야 한다.
    check("시간표는 여전히 나온다", client.get("/api/timetable", headers=USER).status_code == 200)

    print("\n[13] /me는 승인 게이트를 지나지 않는다")
    # 승인 대기 중인 사람도 자기 상태는 알아야 안내 화면을 볼 수 있다.
    me = client.get("/api/me", headers=USER)
    check("200", me.status_code == 200, me.text)
    check("승인 여부가 실린다", me.json().get("isApproved") is True, me.json())
    check("로그인 없이는 401", client.get("/api/me").status_code == 401)

    print()
    if failures:
        raise SystemExit(f"{len(failures)}개 실패: {failures}")
    print("전부 통과.")


if __name__ == "__main__":
    main()
