"""땡시 연습(Spotter)이 쓰는 경로. 과목 다섯이 한 앱이다.

**문은 로그인 하나다.** Study_EZ의 경로가 사람의 승인을 기다리는 것과 갈린다 —
저기서 나가는 것은 남이 만든 강의 필기라 「이 학년 학생인가」를 사람이 확인해야
하지만, 여기 있는 것은 우리가 만든 문항과 실습 정리본 사진이다. 가입하면 열린다.

과목(`SUBJECTS`)은 갈래지 앱이 아니다. 해부학 넷과 기생충학이 문 하나를
같이 쓰고, 로그인하면 다섯이 다 열린다. 갈리는 것은 R2 키와 사이트 경로뿐이다.

그 차이는 이 파일이 아니라 `models.APP_POLICY`에 한 줄로 적혀 있다
(`spotter: auto`). 여기서는 `require_spotter`를 지나는 것이 전부이고, 세 번째
앱도 정책 한 줄만 고르면 같은 자리에 붙는다.

계정은 같다. 같은 Supabase, 같은 `profile` 표를 쓰므로 두 앱에 각각 가입할
필요가 없다. 승인(`is_approved`)은 Study_EZ 쪽 화면에서만 의미를 갖는다.

R2 키는 `spotter/<과목>/` 아래에 모은다. Study_EZ의 강의 자료와 같은 버킷을
쓰되 접두사로 갈라 둔다 — 버킷을 따로 두면 자격증명이 한 벌 더 늘고, 그것이
이 분리가 막아 주는 것보다 크다.

**2026-09-14 에 한 파일 1008줄을 관심사 다섯으로 갈랐다.** 이 파일은 그 다섯을
하나의 라우터로 다시 묶는 것 말고는 아무것도 하지 않는다.

**묶는 순서가 곧 경로를 고르는 순서다.** 가른 뒤에 순서를 바꾸면 겹치는 경로의
승자가 바뀔 수 있어서, 갈리기 전 파일에 있던 순서를 그대로 둔다.
"""

from fastapi import APIRouter

from app.routes.spotter import content, reports, state, threads, uploads
from app.routes.spotter.common import (
    DEFAULT_SUBJECT,
    MAX_SIGN,
    PREFIX,
    SUBJECTS,
    require_spotter,
)

router = APIRouter(prefix="/spotter", tags=["spotter"])
for _part in (content, state, reports, threads, uploads):
    router.include_router(_part.router)

# 가르기 전에 `from app.routes.spotter import ...` 로 꺼내 쓰던 것들. **패키지의
# 표면은 안 바뀐다** — 부르는 쪽이 어느 모듈에 들어갔는지 알 필요가 없다.
# `ensure_threads` 는 `server/tests/test_spotter_reports.py` 가 부른다.
ensure_threads = threads.ensure_threads

__all__ = [
    "DEFAULT_SUBJECT", "MAX_SIGN", "PREFIX", "SUBJECTS",
    "ensure_threads", "require_spotter", "router",
]
