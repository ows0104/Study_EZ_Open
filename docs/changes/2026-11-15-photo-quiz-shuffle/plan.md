# Main-Quiz 사진 판 순서 선택 — 구현 계획

승인: 사용자 요청과 범위 답(2026-11-15). #185·#190과 같은 파일이지만 다른 줄 — 사용자 「지금 진행」. 병합(=배포)은 따로 묻는다.

## 파일

- `server/app/root_learning/planning.py`: `shuffled(tasks, seed)` — 과제 ID와 seed의 해시 순(넣은 순서와 무관한 고정 순서).
- `server/app/routes/root_learning.py`: 시작 요청 `order`(없으면 예전과 같음), `orderable`, overview `orderChoice`·`order`,
  새 회차·더 풀기·이어 풀기·칩 변경(refocus)에서 순서 적용. 세션 state에 `order`.
- `web/src/bank/quizMode.ts`(기기 기억), `RootToday.tsx`(선택 버튼), `RootLearning.tsx`(시작 요청), `types/rootLearning.ts`.
- 검사: `server/tests/test_root_photo_order.py`, `web/tests/root-today-order.{html,tsx}`.

## 위험·복원

- 낮음: 사진 판의 회차 순서만 바뀐다. 복원은 `git revert`. 이미 만든 랜덤 회차는 그날만 남는다.
