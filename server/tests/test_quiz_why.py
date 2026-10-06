"""예습 카드의 「왜 냈나」와 도전 문제가 앞면까지 오는가 — 2026-10-04.

생소한 문제를 본 학생이 「이것까지 알아야 하나?」 싶지 않게 **왜 냈는지**를
질문과 함께 보인다. 답이 아니므로 `reveal` 전에, 문항 목록에서 준다.

  · 러너가 보낸 두 칸이 표를 지나 앞면 목록에 그대로 온다
  · 그 전 러너(두 칸이 없다)가 보낸 문항도 그대로 받는다 — 빈 값이 된다
  · 사람이 뺐다가 되돌린 카드도 두 칸을 잃지 않는다(`cards._CARD_FIELDS`)

    server/.venv/Scripts/python.exe -m tests.test_quiz_why
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="studyez-quizwhy-"))
os.environ.update(
    ENVIRONMENT="local-test",
    DATABASE_URL=f"sqlite:///{(_TMP / 'why.db').as_posix()}",
    STUDYEZ_LOCAL_STORAGE_DIR=str(_TMP / "storage"),
    PUBLIC_API_BASE_URL="http://testserver",
    RUNNER_TOKEN="runner-token",
)

import datetime  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Lecture  # noqa: E402

USER = {"Authorization": "Bearer local-test-token"}
RUNNER = {"Authorization": "Bearer runner-token"}
SUBJECT, RUN = "병리학", "261004_01"
BASE = f"/api/lectures/{SUBJECT}/{RUN}"
ADMIN = f"/api/admin/lectures/{SUBJECT}/{RUN}"

failures: list[str] = []


def check(label: str, condition: bool, detail: object = "") -> None:
    print(f"  {'PASS' if condition else 'FAIL'}  {label}" + (f"  <- {detail}" if not condition else ""))
    if not condition:
        failures.append(label)


def an_item(item_id: str, **extra) -> dict:
    item = {
        "id": item_id, "qtype": "basic", "stem": f"{item_id} 문항", "answer": f"{item_id} 답",
        "explanation": "", "focus": "clinical", "card_type": "term", "exam_hit": False,
        "slide_no": None, "source_type": "lecture", "source_anchor": "", "flags": [],
    }
    item.update(extra)
    return item


def main() -> None:
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        db.add(Lecture(subject=SUBJECT, run_id=RUN, uid=f"{RUN}#x",
                       date=datetime.date(2026, 10, 4), slot=1, slot_end=1,
                       start_time="09:00", title="심근경색", professors=[], author="",
                       version=1))
        db.commit()

    client = TestClient(app)
    items = [
        an_item("c001", why_asked="심근경색 진단에서 가장 먼저 오르는 표지자다", challenge=True,
                why_tags=["exam", "clinical"], learning_support={
                    "hint": "분류 기준을 떠올려 보자", "scope": "기준 하나만 알면 충분하다",
                    "lecture_focus": "기준의 적용을 들어보자", "preview_excerpt": "관리자용 원문"}),
        an_item("c002", why_asked="강의 후반 감별 내내 이 축으로 가른다"),
        an_item("c003"),  # 2026-10-04 전 러너 — 두 칸이 없다
    ]
    put = client.put(f"{ADMIN}/pre-items", json={"items": items}, headers=RUNNER)
    check("두 칸이 실린 문항을 받는다", put.status_code == 200, put.text)

    got = {i["itemId"]: i for i in client.get(f"{BASE}/prequiz", headers=USER).json()["items"]}
    # 앞면에는 배지만 — 글은 답을 편 뒤다. 도전 문제의 「어디서 풀린다」가 답을 흘린다.
    check("왜 냈나 글은 앞면 목록에 없다", "whyAsked" not in got["c001"], sorted(got["c001"]))
    revealed = client.post(f"{BASE}/prequiz/reveal", json={"itemId": "c001"}, headers=USER).json()
    check("왜 냈나 글은 답을 펴면 온다",
          revealed.get("whyAsked") == "심근경색 진단에서 가장 먼저 오르는 표지자다", revealed)
    old = client.post(f"{BASE}/prequiz/reveal", json={"itemId": "c003"}, headers=USER).json()
    check("두 칸이 없던 문항은 편 뒤에도 빈 값이다", old.get("whyAsked") == "", old)
    check("도전 문제 표시가 온다",
          (got["c001"]["challenge"], got["c002"]["challenge"]) == (True, False))
    check("배지 유형이 순서대로 온다", got["c001"]["whyTags"] == ["exam", "clinical"], got["c001"])
    check("두 칸이 없던 문항은 빈 값이다",
          (got["c003"]["challenge"], got["c003"]["whyTags"]) == (False, []), got["c003"])
    check("답은 여전히 앞면 목록에 없다", "answer" not in got["c001"], sorted(got["c001"]))
    check("앞면에는 접근 힌트만 온다", got["c001"].get("hint") == "분류 기준을 떠올려 보자"
          and not got["c001"].get("learningScope") and "learning_support" not in got["c001"])
    check("답 뒤에는 범위와 수업 질문이 온다", revealed.get("learningScope") == "기준 하나만 알면 충분하다"
          and revealed.get("lectureFocus") == "기준의 적용을 들어보자")
    check("관리자용 발췌는 학생에게 오지 않는다", "관리자용 원문" not in str(got) + str(revealed))
    check("옛 카드의 지원 칸은 빈 값이다", old.get("learningScope") == "" and got["c003"].get("hint") == "")
    grade = client.post(f"{BASE}/prequiz/grade", json={"itemId": "c001", "grade": "again"}, headers=USER)
    check("도전은 오답과 복습 일정에 들어가지 않는다", grade.status_code == 409, grade.text)
    progress = client.get(BASE, headers=USER).json()["prequiz"]
    check("진행률은 핵심만 센다", progress["itemCount"] == 2 and progress["due"] == 2, progress)

    # ── 뺐다가 되돌려도 두 칸이 산다. 되돌리기는 원본 사본에서 칸을 하나씩 옮겨 적는다.
    admin = {"Authorization": "Bearer local-test-token"}
    gone = client.put(f"{ADMIN}/cards/pre/c001",
                      json={"action": "delete"}, headers=admin)
    back = client.delete(f"{ADMIN}/cards/pre/c001", headers=admin)
    check("카드를 빼고 되돌릴 수 있다", (gone.status_code, back.status_code) == (200, 200),
          (gone.status_code, gone.text[:120], back.status_code, back.text[:120]))
    got = {i["itemId"]: i for i in client.get(f"{BASE}/prequiz", headers=USER).json()["items"]}
    back_ = client.post(f"{BASE}/prequiz/reveal", json={"itemId": "c001"}, headers=USER).json()
    check("되돌린 카드가 두 칸을 잃지 않는다",
          "c001" in got and got["c001"]["challenge"] and back_.get("whyAsked")
          and got["c001"]["whyTags"] == ["exam", "clinical"],
          (got.get("c001"), back_.get("whyAsked")))
    check("되돌려도 학습 지원이 보존된다", got["c001"].get("hint") == "분류 기준을 떠올려 보자"
          and back_.get("learningScope") == "기준 하나만 알면 충분하다")

    print()
    if failures:
        print(f"{len(failures)}개 실패: {', '.join(failures)}")
        raise SystemExit(1)
    print("전부 통과.")


if __name__ == "__main__":
    main()
