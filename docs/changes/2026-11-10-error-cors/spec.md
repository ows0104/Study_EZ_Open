# 서버 500에도 CORS 헤더 — 설계

## 요구사항과 수용 기준

- R1. 라우트에서 처리되지 않은 예외가 나면 응답은 `500`, 본문 `{"detail": "Internal Server Error"}`이다.
- R2. 요청의 `Origin`이 `CORS_ALLOWED_ORIGINS`에 있으면 그 500 응답에 `Access-Control-Allow-Origin: <Origin>`과 `Vary: Origin`이 붙는다.
- R3. 허용 목록에 없는 출처나 `Origin` 없는 요청에는 CORS 헤더가 붙지 않는다.
- R4. 예외는 다시 던져 서버 로그(Cloud Run)에 지금처럼 스택이 남는다.

## 책임·입출력 계약·오류 상태

- `server/app/errors.py`: 가장 바깥에서 예외를 잡아 500을 만들고 CORS 헤더를 붙이는 순수 ASGI 미들웨어.
  `CORSMiddleware` 바깥에 둔다(`add_middleware`는 나중에 넣은 것이 바깥).
- 응답이 이미 시작된 뒤의 예외는 손대지 않고 다시 던진다(헤더를 바꿀 수 없다).
- API 경로·응답 본문 계약은 바뀌지 않는다. 500 본문은 Starlette 기본값과 같은 JSON이다.

## 호환성과 데이터 보존

- DB·저장소·데이터 변경 없음. 웹 변경 없음.
