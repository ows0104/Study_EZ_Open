from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse

from app.config import get_settings
from app.errors import ErrorCORSMiddleware
from app.routes import quiz_publication
from app.routes import connections
from app.routes import (
    admin,
    bank,
    bundles,
    cards,
    feedback,
    lectures,
    lecture_notes,
    local_storage,
    me,
    notes,
    site_prompts,
    notices,
    prequiz,
    prequiz_jobs,
    spotter,
    study_plan,
    study_visibility,
    timetable,
    usage,
)

settings = get_settings()
log = logging.getLogger("studyez")


def warm_main_quiz() -> None:
    """운영 인스턴스가 요청을 받기 전에 Main-Quiz 가벼운 사본을 만든다(root_learning/light.py 첫머리).

    Cloud Run은 이 함수가 끝나 포트가 열린 뒤에야 새 인스턴스·새 판에 요청을 보낸다. 그래서 배포 직후 첫 강의 목록이
    공개 판 전부를 읽지 않는다. 실패해도 서버는 뜬다 — 그때는 예전처럼 첫 요청이 만든다."""
    from app.database import SessionLocal
    from app.root_learning import content, light
    if not content.globally_enabled():
        return
    try:
        with SessionLocal() as db:
            built, seconds = light.warm(db)
        log.warning("Main-Quiz 가벼운 사본 %d편을 미리 만들었습니다 (%.1f s)", built, seconds)
    except Exception:
        log.exception("Main-Quiz 가벼운 사본 미리 만들기 실패 — 첫 요청이 만든다")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # 운영에서만. 검사·로컬 서버는 각자 DB를 세우기 전에 앱을 띄우므로 여기서 읽지 않는다.
    if settings.environment == "production" and os.getenv("STUDYEZ_WARM_MAIN_QUIZ", "1") != "0":
        warm_main_quiz()
    yield


app = FastAPI(
    lifespan=lifespan,
    title="Study_EZ API",
    version="1.0.0",
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_allowed_origins),
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    # Range/Accept-Ranges/Content-Range: PDF.js reads only the pages it draws from the
    # Main-Quiz reference PDF stream (routes/root_learning.py read_source).
    allow_headers=["Authorization", "Content-Type", "Range"],
    expose_headers=["Accept-Ranges", "Content-Range", "Content-Length"],
)
# CORS 바깥에 둔다(나중에 넣은 것이 바깥). 처리되지 않은 예외의 500에도 같은 출처 헤더를
# 붙여, 브라우저가 서버 오류를 「Failed to fetch」로 숨기지 않게 한다 — `app/errors.py`.
app.add_middleware(ErrorCORSMiddleware, allow_origins=settings.cors_allowed_origins)


@app.get("/robots.txt", response_class=PlainTextResponse, include_in_schema=False)
def robots() -> str:
    # API에는 크롤러가 가져갈 것이 없다. 로그인 없이는 어느 경로도 열리지 않으므로
    # 색인을 막는 헤더를 따로 두지 않는다 — 관문은 로그인 하나다.
    return "User-agent: *\nDisallow: /api/\n"


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "environment": settings.environment,
            "revision": os.getenv("STUDYEZ_REVISION", "")}


app.include_router(me.router, prefix="/api")
app.include_router(notes.router, prefix="/api")
app.include_router(connections.router, prefix="/api")
app.include_router(feedback.router, prefix="/api")
app.include_router(timetable.router, prefix="/api")
app.include_router(quiz_publication.router, prefix="/api")
app.include_router(study_plan.router, prefix="/api")
app.include_router(study_visibility.router, prefix="/api")
app.include_router(lectures.router, prefix="/api")
app.include_router(lecture_notes.router, prefix="/api")
# 여러 편의 덱을 한 파일로. **합치는 것은 브라우저다** — 여기는 목록과 서명만 준다
# (`routes/bundles.py` 첫머리에 왜인지 적혀 있다).
app.include_router(bundles.router, prefix="/api")
app.include_router(prequiz.router, prefix="/api")
app.include_router(admin.router, prefix="/api/admin")
app.include_router(site_prompts.router, prefix="/api/admin")
# 러너 일감 큐. `admin` 에서 갈라 나왔고 붙는 자리는 같다 — 주소가 바뀌면 안 된다.
app.include_router(prequiz_jobs.router, prefix="/api/admin")
# 사람별 이용현황. 읽기만 하는 집계라 `admin` 에서 따로 섰다 — 붙는 자리는 같다.
app.include_router(usage.router, prefix="/api/admin")
# 걸린 카드를 사이트에서 고친다(2026-09-23). 붙는 자리는 같다.
app.include_router(cards.router, prefix="/api/admin")
# 공지사항(2026-10-04). 읽기는 `/api`, 쓰기는 `/api/admin` — 한 파일에 둘이다.
app.include_router(notices.router, prefix="/api")
# Quiz Bank(2026-10-04) — 학생 풀이와 관리자·러너의 넣고 받기.
app.include_router(bank.router, prefix="/api")
app.include_router(bank.admin_router, prefix="/api/admin")
app.include_router(notices.admin_router, prefix="/api/admin")
# 기생충학 땡시. **승인 게이트를 안 지난다** — 가입하면 열린다.
# 이유는 `routes/spotter/__init__.py` 첫머리에 있다.
app.include_router(spotter.router, prefix="/api")
app.include_router(local_storage.router, prefix="/api")

from app.routes import root_learning
app.include_router(root_learning.router, prefix="/api")

from app.routes import root_generation
app.include_router(root_generation.router, prefix="/api")

from app.routes import jokbo
app.include_router(jokbo.router, prefix="/api")
app.include_router(jokbo.admin_router, prefix="/api/admin")
