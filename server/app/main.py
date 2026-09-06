from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse

from app.config import get_settings
from app.routes import (
    admin,
    lectures,
    local_storage,
    me,
    prequiz,
    prequiz_jobs,
    spotter,
    timetable,
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
app.include_router(prequiz.router, prefix="/api")
app.include_router(admin.router, prefix="/api/admin")
# 러너 일감 큐. `admin` 에서 갈라 나왔고 붙는 자리는 같다 — 주소가 바뀌면 안 된다.
app.include_router(prequiz_jobs.router, prefix="/api/admin")
# 기생충학 땡시. **승인 게이트를 안 지난다** — 가입하면 열린다.
# 이유는 `routes/spotter.py` 첫머리에 있다.
app.include_router(spotter.router, prefix="/api")
app.include_router(local_storage.router, prefix="/api")
