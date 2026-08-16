from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routes import admin, lectures, local_storage, prequiz, timetable


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


@app.middleware("http")
async def block_indexing(request: Request, call_next):
    """색인 차단은 옵션이 아니다.

    작년 필기와 족보는 제3자 저작물이다. 파일 자체는 서명 URL 뒤에 있지만 강의
    제목과 문항 본문도 남의 것이므로, API가 내보내는 모든 응답에 붙인다.
    """
    response = await call_next(request)
    response.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive, nosnippet"
    return response


@app.get("/robots.txt", response_class=PlainTextResponse, include_in_schema=False)
def robots() -> str:
    return "User-agent: *\nDisallow: /\n"


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "environment": settings.environment}


app.include_router(timetable.router, prefix="/api")
app.include_router(lectures.router, prefix="/api")
app.include_router(prequiz.router, prefix="/api")
app.include_router(admin.router, prefix="/api/admin")
app.include_router(local_storage.router, prefix="/api")
