# 구현 계획

승인: 사용자 요청(2026-11-14) 자체가 구현 지시. 「회독 이제 병합됐으니까 작업 시작하고 merge까지 자동으로 진행해」(2026-11-15)로 master 병합(=자동 배포)까지 승인.

## 파일

1. `web/src/jokbo/JokboPage.tsx`: `JokboSolve`에 `undo`. 결과마다 고르기 전 표시(`before`)를 남기고, z면 index를 하나 되돌려 답 화면을 연다.
   표시 되돌림은 기존 `onRate`(같으면 쓰지 않음, 채점 기록 뒤에 씀)로. `onRate`가 예전 low도 받도록 타입을 넓힘.
2. `web/src/notices/GuidePage.tsx`: 족보 단축키 한 줄.
3. `web/tests/jokbo-undo.{html,tsx}`: 가짜 fetch 고정물.

## 검사

- `web/`에서 `npx tsc -b --noEmit`, `npm run build`, `node --test tests/jokbo-selection.test.cjs`.
- vite 고정물 `tests/jokbo-undo.html`(운영 DB·API 미사용).

## 위험·복원

- 웹만 바뀐다. 복원은 `git revert`.
