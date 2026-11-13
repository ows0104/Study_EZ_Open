# Main-Quiz 자료 충돌 배지 — 구현 계획

## 파일
- `web/src/bank/BankSourceNote.tsx`: `SourceConflictBadge`(기존 `sourceNote` 파서 사용).
- `web/src/bank/BankQuestion.tsx`: `AnswerBody`의 `reviewInline={false}` 경로에 한 줄.
- `web/src/bank/source-notes.css`: 배지 블록.
- `web/tests/root-conflict-badge.{html,tsx}` + `web/tests/bank-interactions.test.cjs` 목록 한 항목.

`RootSolve.tsx`는 Draft PR #137(선지 접기)이 고치고 있어 건드리지 않는다.

## 검사
- `npm --prefix web run typecheck`, `npm --prefix web run build`.
- vite(5199) + 고정물 `root-conflict-badge`·회귀 `choice-explanations`·`root-solve-bar`·`root-choice-keys`. 운영 DB·API 미사용.

## 위험·복원
- 화면 표시만. 복원은 PR revert.
