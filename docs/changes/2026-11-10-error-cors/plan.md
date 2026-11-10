# 서버 500에도 CORS 헤더 — 구현 계획

구현 승인: 사용자 2026-11-10 「500에 CORS도 붙여줘」, 대시보드 겹침(main.py, 회독·메모 PR #79) 확인 뒤 「진행해」.

## 변경 범위·대상 파일·순서

| 순서 | 파일 | 내용 |
|---|---|---|
| 1 | `server/app/errors.py` (새 파일) | 예외 → 500 + 허용 출처 CORS 헤더 미들웨어 |
| 2 | `server/app/main.py` | `CORSMiddleware` 다음에 위 미들웨어 등록(몇 줄) |
| 3 | `server/tests/test_error_cors.py` (새 파일) | R1–R3 검사 |

## 검사 명령과 성공 조건

- `server/.venv/Scripts/python.exe -m tests error_cors` 통과.
- `server/.venv/Scripts/python.exe -m tests` 전체에서 새 실패 없음(기존 환경 실패는 원인과 함께 적는다).

## 위험·복원·승인할 범위

- 위험: 미들웨어가 정상 응답을 바꾸는 것. 검사에서 정상·4xx 응답 헤더가 그대로인지 본다.
- 복원: PR revert.
- master 병합(=운영 API 자동 배포)은 별도 승인.
