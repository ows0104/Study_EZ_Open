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
        an_item("c001", why_asked="심근경색 진단에서 가장 먼저 오르는 표지자다", challenge=True),
        an_item("c002", why_asked="강의 후반 감별 내내 이 축으로 가른다"),
        an_item("c003"),  # 2026-10-04 전 러너 — 두 칸이 없다
    ]
    put = client.put(f"{ADMIN}/pre-items", json={"items": items}, headers=RUNNER)
    check("두 칸이 실린 문항을 받는다", put.status_code == 200, put.text)

    got = {i["itemId"]: i for i in client.get(f"{BASE}/prequiz", headers=USER).json()["items"]}
    check("왜 냈나가 앞면 목록에 온다",
          got["c001"]["whyAsked"] == "심근경색 진단에서 가장 먼저 오르는 표지자다", got["c001"])
    check("도전 문제 표시가 온다",
          (got["c001"]["challenge"], got["c002"]["challenge"]) == (True, False))
    check("두 칸이 없던 문항은 빈 값이다",
          (got["c003"]["whyAsked"], got["c003"]["challenge"]) == ("", False), got["c003"])
    check("답은 여전히 앞면 목록에 없다", "answer" not in got["c001"], sorted(got["c001"]))

    # ── 뺐다가 되돌려도 두 칸이 산다. 되돌리기는 원본 사본에서 칸을 하나씩 옮겨 적는다.
    admin = {"Authorization": "Bearer local-test-token"}
    gone = client.put(f"{ADMIN}/cards/pre/c001",
                      json={"action": "delete"}, headers=admin)
    back = client.delete(f"{ADMIN}/cards/pre/c001", headers=admin)
    check("카드를 빼고 되돌릴 수 있다", (gone.status_code, back.status_code) == (200, 200),
          (gone.status_code, gone.text[:120], back.status_code, back.text[:120]))
    got = {i["itemId"]: i for i in client.get(f"{BASE}/prequiz", headers=USER).json()["items"]}
    check("되돌린 카드가 두 칸을 잃지 않는다",
          "c001" in got and got["c001"]["challenge"] and got["c001"]["whyAsked"],
          got.get("c001"))

    print()
    if failures:
        print(f"{len(failures)}개 실패: {', '.join(failures)}")
        raise SystemExit(1)
    print("전부 통과.")


if __name__ == "__main__":
    main()
