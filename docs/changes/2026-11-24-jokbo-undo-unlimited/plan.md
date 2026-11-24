# 족보 풀이 Z 무제한·답 선택 취소 — 구현 계획

## 변경 범위·대상 파일·순서

1. `server/app/routes/jokbo.py`: answer 응답에 `before`, 새 `answer/undo`.
2. `server/tests/test_jokbo.py`: 취소 후 횟수·표시·시각 복원, 처음 푼 줄 삭제, 409·422.
   `server/tests/test_route_contract.py`에 경로 추가.
3. `web/src/jokbo/marks.tsx`: 문항별 순서 큐와 답 기록·표시·취소를 묶은 `useMarkWriter`, `undoAnswer` API.
4. `web/src/jokbo/JokboPage.tsx`·`JokboMix.tsx`: 훅 사용, `JokboSolve`에 `onUnanswer`, Z 무제한.
5. `web/src/types/jokbo.ts`: 응답 `before`.
6. `web/src/notices/GuidePage.tsx`: 족보 Z 설명.
7. `web/tests/jokbo-undo.tsx`: 새 동작 고정물.

## 검사 명령과 성공 조건

- `server/`에서 `.venv/Scripts/python.exe -m tests jokbo`, `-m tests route_contract`(격리 로컬 DB) 통과.
- `web/`에서 `npm run typecheck`, `npm run build`, `node --test tests/jokbo-selection.test.cjs tests/jokbo-mix.test.cjs` 통과.
- vite 고정물 `tests/jokbo-undo.html`(가짜 fetch, 운영 API 미사용)이 ALL PASSED.

## 위험·복원·승인할 범위

- 새 API는 추가만. 웹이 먼저 배포돼 취소가 404여도 화면은 되돌아가고 기록만 남는다(현재와 같음).
- 복원은 `git revert`. DB 변경 없음.
- 승인 범위: 위 파일의 로컬 구현·검사·PR.
