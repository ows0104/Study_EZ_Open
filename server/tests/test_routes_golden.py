"""경로 목록이 안 바뀌었는가. **구조를 고칠 때 쓰는 자다.**

2026-09-14 에 `routes/spotter.py` 1008줄을 관심사 다섯으로 가르면서 세웠다.
그런 리팩터의 위험은 예외가 아니라 **조용한 사라짐**이다 — 라우터를 묶는 순서를
잘못 두거나 `include_router` 를 하나 빼먹으면 경로가 통째로 없어지는데, 서버는
멀쩡히 뜨고 나머지 검사도 다 통과한다. 사라진 경로를 부르는 화면만 404를 받는다.

그래서 여기서는 **경로와 메서드의 목록**만 본다. 응답의 내용은 다른 검사들이 본다.

    server/.venv/Scripts/python.exe -m tests.test_routes_golden

목록이 바뀌면 먼저 **왜 바뀌었는지 답하고**, 의도한 것이면 그때 `GOLDEN` 을 고친다.
숫자를 먼저 맞추면 이 검사는 아무것도 안 막는다.
"""

from __future__ import annotations

import os
from pathlib import Path

_TMP = Path(__file__).resolve().parent.parent / "local_test_data"
_TMP.mkdir(exist_ok=True)
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_TMP / 'routes.db'}")
os.environ.setdefault("ENVIRONMENT", "local-test")

from app.main import app  # noqa: E402

# 2026-09-14 의 목록. 가르기 전과 후가 한 줄도 다르지 않은 것을 확인한 값이다.
GOLDEN = """
DELETE /api/lectures/{subject}/{run_id}/mainquiz/attempts
DELETE /api/lectures/{subject}/{run_id}/prequiz/attempts
DELETE /api/spotter/comments/{comment_id}
GET /api/admin/lectures/{subject}/{run_id}/prequiz-job
GET /api/admin/overview
GET /api/admin/prequiz-jobs
GET /api/admin/previews
GET /api/admin/timetable-events
GET /api/admin/usage
GET /api/admin/usage/{user_id}
GET /api/admin/users
GET /api/bundles/decks
GET /api/bundles/decks/{subject}/{run_id}/{kind}
GET /api/health
GET /api/lectures/{subject}/{run_id}
GET /api/lectures/{subject}/{run_id}/files/{asset_id}
GET /api/lectures/{subject}/{run_id}/mainquiz
GET /api/lectures/{subject}/{run_id}/prequiz
GET /api/local-storage/{object_key}
GET /api/me
GET /api/me/preview-prompt
GET /api/spotter/admin/reports
GET /api/spotter/admin/subjects/{subject}/manifest
GET /api/spotter/db
GET /api/spotter/flagged
GET /api/spotter/reports/mine
GET /api/spotter/state
GET /api/spotter/subjects/{subject}/db
GET /api/spotter/threads
GET /api/spotter/threads/{kind}/{subject}
GET /api/timetable
PATCH /api/spotter/admin/reports/{report_id}
PATCH /api/spotter/admin/threads/{kind}/{subject}
POST /api/admin/lectures
POST /api/admin/lectures/{subject}/{run_id}/prequiz-job
POST /api/admin/lectures/{subject}/{run_id}/uploads
POST /api/admin/lectures/{subject}/{run_id}/uploads/complete
POST /api/admin/prequiz-jobs/claim
POST /api/admin/prequiz-jobs/{job_id}/cancel
POST /api/admin/prequiz-jobs/{job_id}/move
POST /api/bundles/grabs
POST /api/lectures/{subject}/{run_id}/mainquiz/grade
POST /api/lectures/{subject}/{run_id}/mainquiz/reveal
POST /api/lectures/{subject}/{run_id}/mainquiz/undo
POST /api/lectures/{subject}/{run_id}/preview-open
POST /api/lectures/{subject}/{run_id}/prequiz/grade
POST /api/lectures/{subject}/{run_id}/prequiz/reveal
POST /api/lectures/{subject}/{run_id}/prequiz/undo
POST /api/spotter/admin/reports/{question_id}/close
POST /api/spotter/admin/subjects/{subject}/db/refresh
POST /api/spotter/admin/subjects/{subject}/uploads
POST /api/spotter/finish
POST /api/spotter/images/sign
POST /api/spotter/reports
POST /api/spotter/state/merge
POST /api/spotter/subjects/{subject}/images/sign
POST /api/spotter/threads/{kind}/{subject}/comments
PUT /api/admin/course-aliases
PUT /api/admin/lectures/{subject}/{run_id}/main-items
PUT /api/admin/lectures/{subject}/{run_id}/match
PUT /api/admin/lectures/{subject}/{run_id}/pre-items
PUT /api/admin/lectures/{subject}/{run_id}/preview
PUT /api/admin/lectures/{subject}/{run_id}/run-meta/{quiz_kind}
PUT /api/admin/lectures/{subject}/{run_id}/waive
PUT /api/admin/prequiz-jobs/{job_id}
PUT /api/admin/users/{user_id}/approval
PUT /api/lectures/{subject}/{run_id}/my-preview
PUT /api/local-storage/{object_key}
PUT /api/me/preview-prompt
"""


def current() -> list[str]:
    spec = app.openapi()
    rows = [f"{method.upper()} {path}"
            for path, ops in spec["paths"].items() for method in ops]
    return sorted(rows)


def main() -> None:
    want = sorted(line for line in GOLDEN.strip().split("\n") if line)
    got = current()
    missing = [r for r in want if r not in got]
    extra = [r for r in got if r not in want]

    print(f"경로 {len(got)}개")
    ok = not missing and not extra
    print(f"  {'PASS' if ok else 'FAIL'}  목록이 그대로다")
    for r in missing:
        print(f"        사라짐: {r}")
    for r in extra:
        print(f"        새로 생김: {r}")

    if not ok:
        print("\n실패 1")
        raise SystemExit(1)
    print("\n모두 통과")


if __name__ == "__main__":
    main()
