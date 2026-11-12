# 퀴즈 풀이 중 뒤로가기 — 구현 계획

승인: 사용자 요청(2026-11-12) 자체가 이 범위의 구현 지시. master 병합(=자동 배포)은 별도 승인.

## 파일

1. `web/src/bank/RootSolve.tsx`: 머리줄 `.mq-kicker` 앞에 `.quiz-back` 버튼(`onToday`, 진행 중 비활성).
2. `web/src/bank/main-quiz.css`: `.quiz-back` 스타일.
3. `web/src/lecture/PreQuiz.tsx`: `useNavigate`, `leave()`(history idx>0이면 -1, 아니면 `/`), 머리줄 버튼.
4. `web/src/lecture/prequiz.css`: `.quiz-back` 스타일(Main-Quiz css는 그 화면에서만 불러오므로 따로 둔다).

## 검사

- `web/`에서 `npm run build`(tsc 포함).
- 브라우저: 격리 fixture API(`tests.serve_root_fixture`, 8027) + vite(5199)로 `web/tests/root-learning.html`,
  메모리 대체 `web/tests/prequiz.html`.

## 위험·복원

- 위험 낮음: 화면 버튼만 추가. 복원은 `git revert`.
