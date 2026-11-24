# 족보 풀이 Z 무제한·답 선택 취소 — 배포 준비

## 코드 리뷰·검증 결과

- 서버 `answer/undo`: 내 줄의 `last_result`가 보낸 결과와 같을 때만 되돌린다(409). 횟수는 0 아래로 가지 않고,
  남는 기록이 없으면 줄을 지운다. 다른 사람 줄은 user_id 기본 키라 닿지 않는다.
- 웹 `useMarkWriter`: 같은 문항의 답 기록 → 표시 → 답 취소를 한 줄로 보낸다. 답 기록이 실패하면 취소를 보내지 않는다.
  같은 문항을 다른 판에서 다시 풀어도 가장 최근 답부터 취소한다.
- `server`: `-m tests jokbo`, `route_contract`, `usage` 통과(격리 sqlite, 운영 DB 미사용). 새 검사: 처음 푼 줄 삭제,
  사람이 붙인 표시·시각 복원, 두 번째 풀이만 취소, 409·422.
- `web`: typecheck·build 통과. vite 고정물 `tests/jokbo-undo.html` 21항목 ALL PASSED(가짜 fetch).
  `tests/jokbo-selection.test.cjs` 통과.
- 실행하지 못한 검사: `tests/jokbo-mix.test.cjs`는 Playwright가 이 PC에 없어 실행하지 못했다(master에서도 같은 오류, CI 미포함).
  모아풀기는 같은 `JokboSolve`·`useMarkWriter`를 쓰고 키만 `splitKey`로 나눈다.

## 배포 대상 버전·순서·데이터 변경

- DB 표·칼럼 변경 없음. 새 API는 추가만, `answer` 응답은 필드 추가만.
- master 병합 시 기존 순서대로 API 먼저, 같은 SHA의 웹이 뒤에 배포된다.

## 배포 후 확인·롤백·필요한 사람 승인

- 확인: 족보 한 강의에서 답 고르기 → Z → 문제 화면으로 돌아오고, 오답노트에 그 문항이 새로 생기지 않는지.
- 롤백: `git revert`. 되돌린 뒤에도 이미 취소된 기록은 이전 값 그대로라 정리할 것이 없다.
- 추가 승인 필요 없음(되돌릴 수 있는 코드 배포).
