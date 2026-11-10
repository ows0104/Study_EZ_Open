"""처리되지 않은 예외의 500에도 CORS 헤더를 붙인다.

Starlette는 처리되지 않은 예외를 가장 바깥의 `ServerErrorMiddleware`에서 500으로 바꾼다.
그 자리는 `CORSMiddleware`보다 바깥이라 500에는 `Access-Control-Allow-Origin`이 없다.
그러면 브라우저는 응답을 화면 코드에 넘기지 않고, 화면에는 「Failed to fetch」만 뜬다
(2026-11-10 자유 노트: 운영 DB에 `user_note` 표가 없어 500이 났는데 네트워크 오류처럼 보였다).

이 미들웨어는 `CORSMiddleware` 바깥에서 예외를 잡아 500을 직접 만들고, 허용된 출처면
같은 헤더를 붙인다. 예외는 다시 던져 서버 로그에 지금처럼 스택이 남는다.
"""

from __future__ import annotations

from collections.abc import Iterable

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send


class ErrorCORSMiddleware:
    def __init__(self, app: ASGIApp, allow_origins: Iterable[str]) -> None:
        self.app = app
        self.allow_origins = frozenset(allow_origins)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        started = False

        async def tracked(message: Message) -> None:
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, receive, tracked)
        except Exception:
            if started:
                raise  # 헤더가 이미 나갔다. 바꿀 수 없다.
            headers = {}
            origin = _origin(scope)
            if origin and origin in self.allow_origins:
                headers = {"Access-Control-Allow-Origin": origin, "Vary": "Origin"}
            response = JSONResponse({"detail": "Internal Server Error"}, status_code=500, headers=headers)
            await response(scope, receive, send)
            raise


def _origin(scope: Scope) -> str | None:
    for key, value in scope.get("headers", ()):
        if key == b"origin":
            return value.decode("latin-1")
    return None
