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

    # 필기는 받는 것이 아니라 보는 것이다. `inline=1`을 주면 첨부가 아니라
    # 인라인으로 서명돼야 새 탭이 내려받기로 바뀌지 않는다.
    notes = next(
        item
        for item in client.get("/api/lectures/병리학/260813_03", headers=USER).json()["files"]
        if item["kind"] == "notes_current"
    )
    signed = f"/api/lectures/병리학/260813_03/files/{notes['id']}"
    attached = httpx.URL(client.get(signed, headers=USER).json()["url"])
    opened = httpx.URL(client.get(f"{signed}?inline=1", headers=USER).json()["url"])
    check("기본은 첨부다", "download" in attached.params, str(attached))
    check("inline=1이면 인라인으로 서명된다", "inline" in opened.params, str(opened))
    served = client.get(opened.path, params=dict(opened.params))
    check(
        "받은 응답도 인라인이다",
        served.headers["content-disposition"].startswith("inline"),
        served.headers.get("content-disposition"),
    )

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

    # 러너가 저장된 링크를 **되읽는** 길. 여기만 방향이 반대다 — 관리자가
    # 저장한 링크를 보고 로컬이 Pre-Quiz를 만든다(`studyez.prequeue`).
    listed = client.get("/api/admin/previews", headers=RUNNER)
    check("러너 토큰으로 목록을 읽는다", listed.status_code == 200, listed.text)
    rows = listed.json()["previews"]
    check("저장한 링크가 그대로 나온다",
          [row["shareUrl"] for row in rows] == ["https://chatgpt.com/share/abc"], rows)
    check("강의 정보가 함께 온다 — 로컬이 작년 짝을 찾는 데 쓴다",
          rows[0]["subject"] == "병리학" and rows[0]["runId"] == "260813_03" and rows[0]["date"],
          rows[0])
    check("/c/는 이 목록으로 안 나간다", "conversationUrl" not in rows[0], rows[0])
    check("로그인 없이는 못 읽는다",
          client.get("/api/admin/previews").status_code in (401, 403))

    print("\n[6] Pre-Quiz — 답이 문제와 함께 나가지 않는가")
    client.put(
        "/api/admin/lectures/병리학/260813_03/pre-items",
        headers=RUNNER,
        json={
            "lecture_id": "260813_03",
            "items": [
                {
                    "id": "c001", "qtype": "basic",
                    "stem": "Proto-oncogene 과 oncogene 은 어떻게 다른가?",
                    "answer": "변이로 자율 작동하게 된 것이 oncogene 이다",
                    "focus": "spine", "card_type": "term", "slide_no": 6,
                    "explanation": "정상 유전자가 켜진 채로 남는다는 틀이다.",
                },
                {
                    "id": "c002", "qtype": "cloze",
                    "stem": "재태 28주 미만에서 RDS 위험은 [____]다.",
                    "answer": "60%", "focus": "mechanism", "card_type": "number",
                },
                {
                    "id": "c003", "qtype": "ox",
                    "stem": "저체중 자체가 RDS의 가장 중요한 위험인자다.",
                    "answer": "X", "focus": "clinical", "card_type": "trap",
                },
            ],
        },
    )
    quiz = client.get("/api/lectures/병리학/260813_03/prequiz", headers=USER).json()
    check("카드 3장", len(quiz["items"]) == 3, quiz)
    leaked = sorted({"answer", "explanation"} & {key for item in quiz["items"] for key in item})
    check("answer·explanation 필드가 없다", not leaked, leaked)
    # 필드 이름을 지웠어도 값이 다른 자리에 실리면 마찬가지다.
    check("답 문자열이 어디에도 없다", "oncogene 이다" not in str(quiz), quiz)

    print("\n[7] 펴 보기와 자기채점")
    opened = client.post(
        "/api/lectures/병리학/260813_03/prequiz/reveal",
        headers=USER, json={"itemId": "c001"},
    ).json()
    check("펴면 답이 온다", opened["answer"].startswith("변이로"), opened)
    check("근거 슬라이드가 붙는다", bool(opened["slideUrl"]), opened)
    # 펴 보기만으로 「풀었다」로 세면 답을 보고 넘긴 카드까지 기록에 섞인다.
    check("펴는 것만으로는 안 남는다",
          client.get("/api/lectures/병리학/260813_03/prequiz", headers=USER).json()["answered"] == 0)

    for item_id, correct in (("c001", False), ("c002", True), ("c003", False)):
        client.post("/api/lectures/병리학/260813_03/prequiz/grade",
                    headers=USER, json={"itemId": item_id, "correct": correct})
    scored = client.get("/api/lectures/병리학/260813_03/prequiz", headers=USER).json()
    check("푼 것 3 · 맞았다고 찍은 것 1",
          (scored["answered"], scored["correct"]) == (3, 1), scored)

    print("\n[8] 놓친 것 — 뼈대가 먼저 오는가")
    detail = client.get("/api/lectures/병리학/260813_03", headers=USER).json()
    missed = detail["prequiz"]["missed"]
    check("두 장을 놓쳤다", len(missed) == 2, missed)
    # `spine`(뼈대)이 `clinical`보다 앞이다. 모르면 그 뒤가 통째로 안 붙는다.
    check("spine이 맨 앞", missed and missed[0]["itemId"] == "c001", missed)
    check("점수가 남았다", detail["prequiz"]["correct"] == 1, detail["prequiz"])

    print("\n[9] 캘린더 — 시간표 칸에 점이 붙는가")
    timetable = client.get("/api/timetable", headers=USER).json()["events"]
    linked = [event for event in timetable if event["lectures"]]
    check("칸 하나에 강의가 붙었다", len(linked) == 1, timetable)
    lecture_ref = linked[0]["lectures"][0]
    marks = lecture_ref["marks"]
    check("올해 필기·예습퀴즈·예습 링크가 켜졌다",
          all(marks[key] for key in ("notesCurrent", "prequiz", "preview")), marks)
    # 작년 필기와 올해 필기는 쓰이는 자리가 다르다 — 앞의 것은 강의 전에 읽는
    # 예습 자리로, 뒤의 것은 강의 후에 받는 복습 자리로 간다. 한 칸으로 묶어
    # 세면 [3]에서 올린 올해 필기 하나가 예습 자리까지 켜 버린다.
    check("작년 필기는 안 올라왔으므로 꺼져 있다", marks["notesPrev"] is False, marks)
    # 이 강의에는 `main_apkg`가 안 올라왔다. 전에는 `pre_item`이 있다는 이유로
    # 본덱 점까지 켜져서, 점만 보고는 시험 대비 덱이 있는지 알 수 없었다.
    check("본덱이 없으면 본퀴즈 점은 꺼져 있다", marks["quiz"] is False, marks)
    # [3]에서 올해 필기의 서명을 받아 갔다. 덱이 "했다"를 말하는 유일한 길이
    # 이것이고, 예습 자리 쪽은 아무것도 안 받았으니 아직 거짓이어야 한다.
    check("받아 간 자리만 참이다", lecture_ref["grabbed"] == {"pre": False, "main": True},
          lecture_ref["grabbed"])
    # [7]에서 세 문항을 모두 채점받았다.
    check("내가 푼 수가 함께 온다",
          lecture_ref["prequizProgress"] == {"total": 3, "answered": 3},
          lecture_ref["prequizProgress"])

    # 로컬 테스트 모드는 사용자가 하나뿐이라 HTTP로는 못 가른다. 집계 함수를
    # 직접 부른다 — 사람이 갈리는 자리가 거기다.
    from app.database import SessionLocal
    from app.routes.common import prequiz_progress
    with SessionLocal() as db:
        theirs = prequiz_progress(db, "someone-else", [("병리학", "260813_03")])
    check("남의 시도는 내 진도에 안 실린다",
          theirs == {("병리학", "260813_03"): {"total": 3, "answered": 0}}, theirs)

    print("\n[10] 로그인 없이는 아무것도 안 나간다")
    check("401", client.get("/api/timetable").status_code == 401)
    check("러너 토큰 없이 등록 불가", client.post("/api/admin/lectures", json=[]).status_code in (401, 403))

    print("\n[10.5] 관리자 체크리스트 — 안 올라온 칸과 닫아 둔 칸")
    overview = "/api/admin/overview"
    waive = "/api/admin/lectures/병리학/260813_03/waive"

    def _checklist():
        rows = client.get(overview, headers=USER).json()["lectures"]
        return next(row for row in rows if row["runId"] == "260813_03")["checklist"]

    check("올린 것은 done", _checklist()["notes_current"] == "done", _checklist())
    check("안 올린 것은 todo", _checklist()["notes_prev"] == "todo", _checklist())
    # 신설 강의에는 작년 필기가 없다. 닫을 길이 없으면 그런 칸이 영영 미완으로
    # 남아 화면이 미완으로 가득 차고, 그러면 정말 밀린 강의가 안 보인다.
    client.put(waive, headers=USER, json={"item": "notes_prev", "waived": True})
    check("닫으면 waived", _checklist()["notes_prev"] == "waived", _checklist())
    # 올라온 것이 닫아 둔 것을 이긴다 — 자료가 있는데 "해당 없음"으로 보이면
    # 화면이 거짓말을 하는 것이다.
    client.put(waive, headers=USER, json={"item": "notes_current", "waived": True})
    check("올라온 칸은 닫아도 done", _checklist()["notes_current"] == "done", _checklist())
    check("모르는 항목은 400",
          client.put(waive, headers=USER, json={"item": "nope"}).status_code == 400)
    client.put(waive, headers=USER, json={"item": "notes_prev", "waived": False})
    check("되돌리면 todo", _checklist()["notes_prev"] == "todo", _checklist())

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

    print("\n[14] Pre-Quiz 일감 — 버튼 한 번이 러너까지 간다")
    # 야간 스케줄러를 걷어내고 이 길로 바꿨다. 관리자가 누르면 줄이 하나 생기고,
    # 노트북이 집어 가고, 진행이 화면으로 돌아온다.
    base14 = "/api/admin/lectures/병리학/260813_03"

    empty = client.post("/api/admin/prequiz-jobs/claim", headers=RUNNER)
    check("집어 갈 일감이 없으면 null", empty.status_code == 200 and empty.json()["job"] is None, empty.text)

    made = client.post(f"{base14}/prequiz-job", headers=USER)
    check("관리자가 누르면 만들어진다", made.status_code == 200 and made.json()["created"] is True, made.text)
    job_id = made.json()["job"]["id"]
    check("queued 로 선다", made.json()["job"]["state"] == "queued", made.json())

    again = client.post(f"{base14}/prequiz-job", headers=USER)
    check("두 번 눌러도 두 번 만들지 않는다",
          again.json()["created"] is False and again.json()["job"]["id"] == job_id, again.text)

    check("러너 토큰으로는 못 누른다 — 사람이 누르는 자리다",
          client.post(f"{base14}/prequiz-job", headers=RUNNER).status_code in (401, 403))

    # 캘린더 패널이 「Pre-Quiz 덱 — 아직 없습니다」 자리에서 읽는 곳.
    one = client.get(f"{base14}/prequiz-job", headers=USER)
    check("편 하나만 따로 읽는다", one.json()["job"]["id"] == job_id, one.text)
    check("러너 상태를 같이 준다", "runner" in one.json(), one.json())
    check("학생은 못 읽는다 — 만드는 것은 관리자 몫이다",
          client.get(f"{base14}/prequiz-job").status_code in (401, 403))

    claimed = client.post("/api/admin/prequiz-jobs/claim", headers=RUNNER)
    check("러너가 집어 간다", claimed.json()["job"]["id"] == job_id, claimed.text)
    check("running 으로 바뀐다", claimed.json()["job"]["state"] == "running", claimed.json())

    twice = client.post("/api/admin/prequiz-jobs/claim", headers=RUNNER)
    check("도는 것이 있으면 새 일감을 안 준다 — 그것을 다시 준다",
          twice.json()["job"]["id"] == job_id, twice.text)

    client.put(f"/api/admin/prequiz-jobs/{job_id}", headers=RUNNER,
               json={"stage": "① 반드시 알아야 할 것"})
    overview14 = client.get("/api/admin/overview", headers=USER).json()
    row14 = next(r for r in overview14["lectures"] if r["runId"] == "260813_03")
    check("진행이 화면까지 온다", row14["prequizJob"]["stage"] == "① 반드시 알아야 할 것", row14["prequizJob"])
    check("러너가 살아 있다고 적힌다", bool(overview14["runner"]["lastSeen"]), overview14["runner"])
    # 한 편을 잡으면 15분 동안 claim 을 안 부른다. 진행을 적는 이 호출이 박동을
    # 겸하지 않으면, 화면이 멀쩡히 만드는 중인 러너를 「안 붙어 있습니다」로 본다.
    check("진행을 적는 것도 박동이다", overview14["runner"]["busy"] is True, overview14["runner"])
    beat = client.put(f"/api/admin/prequiz-jobs/{job_id}", headers=RUNNER, json={})
    check("빈 몸으로도 두드릴 수 있다 — 단계가 그대로인 동안의 박동",
          beat.status_code == 200 and beat.json()["job"]["stage"] == "① 반드시 알아야 할 것", beat.text)

    client.put(f"/api/admin/prequiz-jobs/{job_id}", headers=RUNNER,
               json={"state": "done", "message": "28장"})
    late = client.put(f"/api/admin/prequiz-jobs/{job_id}", headers=RUNNER,
                      json={"state": "running", "stage": "늦게 온 갱신"})
    check("끝난 일감은 다시 열리지 않는다",
          late.json()["applied"] is False and late.json()["job"]["state"] == "done", late.text)

    after = client.post(f"{base14}/prequiz-job", headers=USER)
    check("끝난 뒤에는 다시 누를 수 있다",
          after.json()["created"] is True and after.json()["job"]["id"] != job_id, after.text)
    again_id = after.json()["job"]["id"]
    check("그냥 누른 것은 다시 만드는 일감이 아니다", after.json()["job"]["force"] is False, after.json())

    # 「다시 만들기」. **러너가 이 값을 봐야 한다** — 노트북에 산출물이 남아 있으면
    # `prequeue`가 그 편을 이미 만든 것으로 보고 건너뛴다. 사람이 누른 것을
    # 러너가 알 길은 이 값뿐이다.
    forced = client.post(f"{base14}/prequiz-job", headers=USER, json={"force": True})
    check("줄 서 있는 일감에 「다시 만들기」가 덧붙는다",
          forced.json()["created"] is False
          and forced.json()["job"]["id"] == again_id
          and forced.json()["job"]["force"] is True, forced.text)

    taken = client.post("/api/admin/prequiz-jobs/claim", headers=RUNNER)
    check("러너가 그 값을 받아 간다", taken.json()["job"]["force"] is True, taken.text)

    # 이미 집어 간 뒤에는 늦었다. 러너는 그 편을 이어 만들고 있고 여기서 값만
    # 바꿔도 그 프로세스는 안 본다. 돌려받은 일감의 force 로 화면이 그것을 안다.
    client.put(f"/api/admin/prequiz-jobs/{again_id}", headers=RUNNER, json={"state": "done"})
    plain = client.post(f"{base14}/prequiz-job", headers=USER)
    plain_id = plain.json()["job"]["id"]
    client.post("/api/admin/prequiz-jobs/claim", headers=RUNNER)
    late_force = client.post(f"{base14}/prequiz-job", headers=USER, json={"force": True})
    check("집어 간 뒤에 누른 「다시 만들기」는 안 걸린다 — 화면이 그것을 본다",
          late_force.json()["job"]["id"] == plain_id
          and late_force.json()["job"]["force"] is False, late_force.text)
    client.put(f"/api/admin/prequiz-jobs/{plain_id}", headers=RUNNER, json={"state": "done"})

    fresh = client.post(f"{base14}/prequiz-job", headers=USER, json={"force": True})
    check("끝난 뒤에 누르면 다시 만드는 일감이 새로 선다",
          fresh.json()["created"] is True and fresh.json()["job"]["force"] is True, fresh.text)
    client.put(f"/api/admin/prequiz-jobs/{fresh.json()['job']['id']}", headers=RUNNER,
               json={"state": "done"})

    # 링크가 없는 강의는 거절한다. Pre-Quiz 는 그 대화를 들고 들어가는지 묻는 것이다.
    client.post("/api/admin/lectures", headers=RUNNER, json=[{
        "subject": "병리학", "runId": "260813_01", "uid": "260813_01#링크없음#김혜령",
        "date": "2026-08-13", "slot": 1, "slotEnd": 1, "startTime": "09:00",
        "title": "예습 링크가 아직 없는 강의", "professors": ["김혜령"], "author": "", "version": None,
    }])
    nolink = client.post("/api/admin/lectures/병리학/260813_01/prequiz-job", headers=USER)
    check("예습 링크가 없으면 거절한다", nolink.status_code == 400, nolink.text)
    check("없는 강의는 404", client.post(
        "/api/admin/lectures/병리학/999999_09/prequiz-job", headers=USER).status_code == 404)

    print()
    print("[14-1] 복습 일감 — 같은 우편함, 다른 갈래")
    # 재료가 다르므로 갈래가 있다. 예습은 예습 대화로, 복습은 올해 필기로 만든다.
    # 260813_03에는 [3]에서 올해 필기를 올려 두었다.
    pre_open = client.get(f"{base14}/prequiz-job", headers=USER).json()["job"]
    main = client.post(f"{base14}/prequiz-job?kind=main", headers=USER)
    check("복습도 누르면 만들어진다",
          main.status_code == 200 and main.json()["created"] is True, main.text)
    check("갈래가 실려 온다", main.json()["job"]["kind"] == "main", main.json())
    # 예습 일감이 열려 있어도 복습은 따로 선다. 한 갈래가 다른 갈래를 막지 않는다.
    check("예습 일감이 열려 있어도 새로 선다",
          main.json()["job"]["id"] != pre_open["id"], (main.json(), pre_open))

    check("두 번 눌러도 두 번 만들지 않는다 — 갈래 안에서",
          client.post(f"{base14}/prequiz-job?kind=main", headers=USER).json()["created"] is False)

    # 캘린더 패널이 갈래로 묻는다. 섞어 주면 복습을 만드는 중이라는 말이 예습
    # 자리에 떠서, 사람이 누르지 않은 것을 기다리게 된다.
    read_main = client.get(f"{base14}/prequiz-job?kind=main", headers=USER).json()["job"]
    read_pre = client.get(f"{base14}/prequiz-job?kind=pre", headers=USER).json()["job"]
    check("갈래를 섞어 주지 않는다",
          read_main["id"] == main.json()["job"]["id"] and read_pre["id"] == pre_open["id"],
          (read_main, read_pre))
    check("갈래를 안 주면 예습이다", client.get(
        f"{base14}/prequiz-job", headers=USER).json()["job"]["id"] == pre_open["id"])

    # 올해 필기가 없는 강의(260813_01)는 만들 재료가 없다. 여기서 안 가르면
    # 러너가 15분 뒤에 「만들 자리를 못 찾았다」로 실패한다.
    nonotes = client.post(
        "/api/admin/lectures/병리학/260813_01/prequiz-job?kind=main", headers=USER)
    check("올해 강의록이 없으면 거절한다", nonotes.status_code == 400, nonotes.text)
    check("모르는 갈래는 거절한다", client.post(
        f"{base14}/prequiz-job?kind=quiz", headers=USER).status_code == 400)

    print()
    if failures:
        raise SystemExit(f"{len(failures)}개 실패: {failures}")
    print("전부 통과.")


if __name__ == "__main__":
    main()
