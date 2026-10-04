from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse

from app.config import get_settings
from app.routes import (
    admin,
    bundles,
    cards,
    lectures,
    local_storage,
    me,
    notices,
    prequiz,
    prequiz_jobs,
    spotter,
    timetable,
    usage,
)

settings = get_settings()
app = FastAPI(
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
    allow_headers=["Authorization", "Content-Type"],
)


@app.get("/robots.txt", response_class=PlainTextResponse, include_in_schema=False)
def robots() -> str:
    # API에는 크롤러가 가져갈 것이 없다. 로그인 없이는 어느 경로도 열리지 않으므로
    # 색인을 막는 헤더를 따로 두지 않는다 — 관문은 로그인 하나다.
    return "User-agent: *\nDisallow: /api/\n"


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "environment": settings.environment}


app.include_router(me.router, prefix="/api")
app.include_router(timetable.router, prefix="/api")
app.include_router(lectures.router, prefix="/api")
# 여러 편의 덱을 한 파일로. **합치는 것은 브라우저다** — 여기는 목록과 서명만 준다
# (`routes/bundles.py` 첫머리에 왜인지 적혀 있다).
app.include_router(bundles.router, prefix="/api")
app.include_router(prequiz.router, prefix="/api")
app.include_router(admin.router, prefix="/api/admin")
# 러너 일감 큐. `admin` 에서 갈라 나왔고 붙는 자리는 같다 — 주소가 바뀌면 안 된다.
app.include_router(prequiz_jobs.router, prefix="/api/admin")
# 사람별 이용현황. 읽기만 하는 집계라 `admin` 에서 따로 섰다 — 붙는 자리는 같다.
app.include_router(usage.router, prefix="/api/admin")
# 걸린 카드를 사이트에서 고친다(2026-09-23). 붙는 자리는 같다.
app.include_router(cards.router, prefix="/api/admin")
# 공지사항(2026-10-04). 읽기는 `/api`, 쓰기는 `/api/admin` — 한 파일에 둘이다.
app.include_router(notices.router, prefix="/api")
app.include_router(notices.admin_router, prefix="/api/admin")
# 기생충학 땡시. **승인 게이트를 안 지난다** — 가입하면 열린다.
# 이유는 `routes/spotter/__init__.py` 첫머리에 있다.
app.include_router(spotter.router, prefix="/api")
app.include_router(local_storage.router, prefix="/api")
