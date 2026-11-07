# 구현 — Main-Quiz 로딩 지연 재발

## 바꾼 것

| 파일 | 바꾼 것 |
|---|---|
| `server/app/routes/root_generation.py` | `latest()`의 질의에 `.limit(1)`. 응답 필드·`canonical_generation` 승계·정렬은 그대로 |
| `web/src/bank/pollChain.ts` (새 파일) | `pollAfterSettled(run, delayMs, timers)` — 앞 요청이 끝난 뒤에 다음 것을 센다. 멈추는 함수를 돌려준다 |
| `web/src/bank/RootGenerationPanel.tsx` | 폴링을 `setInterval(…,3000)`에서 `pollAfterSettled(…,3000)`으로. `pending` 판정·`setJob`·`onPublished`·오류 표시·unmount 정리는 그대로 |
| `server/deploy.ps1` | `--concurrency 8` 추가 |
| `server/tests/test_root_generation_poll.py` (새 파일) | 판이 여럿일 때 한 판만 고르는 질의인지, 폴링이 쓰는 필드와 `report`가 그대로인지 |
| `web/tests/root-generation-poll.test.cjs` (새 파일) | 응답 전 미예약 · 거절 뒤 계속 · 멈춤 뒤 미예약 |

## 왜 이 모양인가

`pollAfterSettled`는 `run`의 오류를 삼키고 사슬을 잇는다. 한 번의 실패로 진행 중 작업의
추적을 놓지 않기 위해서다. 오류 표시는 호출하는 쪽(`RootGenerationPanel`)이 그대로 한다.
`timers`를 주입받는 것은 가짜 시계로 "응답 전에는 예약하지 않는다"를 검사하기 위해서다.

동시성 8은 CPU 하나·`uvicorn --workers 1`에 맞춘 값이다. 기본 80은 코어 하나가
감당할 수 없는 수를 한 인스턴스에 쌓는다. 더 낮추면(4) 인스턴스가 더 자주 새로 떠서
콜드스타트를 더 자주 만든다. `--min-instances`·CPU·메모리·`--max-instances`는 바꾸지 않았다.

## 바꾸지 않은 것

- `server/app/routes/root_learning.py:235`의 질의. 그 코드는 판을 **훑어** 같은 revision을
  찾으므로 LIMIT을 붙이면 틀린다.
- 관리자 generation 응답의 필드와 `report` 내용. 폴링 전용 경량 응답은 만들지 않았다 —
  먼저 `.limit(1)`의 효과를 운영에서 재고 판단한다.
- 공부 화면의 `prepare`/`prepare-next`/`prepare-buffer` 세 선취 요청.
- `.github/workflows/deploy.yml`. 그 workflow는 `web/tests/*.test.cjs`를 돌리지 않는다
  (`tests/bridge/*.cjs`와 `web/tests/wait-for-api.test.mjs`만). 새 웹 검사도 기존
  `web/tests/adminPolling.test.cjs`와 같은 처지이며, 아래 명령으로 손으로 돌린다.
- 출제·은행·문항·학습 기록·DB 스키마·사용자 권한.
