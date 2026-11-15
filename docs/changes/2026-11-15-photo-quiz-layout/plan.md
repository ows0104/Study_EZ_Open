# Main-Quiz 사진 문항 화면 — 구현 계획

승인: 사용자 요청(2026-11-15) 자체가 이 범위의 구현 지시. 열린 #185와 같은 파일을 고치는 것도 사용자 확인 후 진행.
master 병합(=자동 배포)은 별도 승인.

## 파일

1. `web/src/bank/RootSolve.tsx`: 카드에 답 연 뒤 `is-answered`, 힌트를 `.quiz-hint` 안의 `.quiz-hint-toggle` 버튼으로.
2. `web/src/bank/main-quiz.css`: Main-Quiz 풀이 안의 `.bank-stimuli` 가운데·높이 제한·답 뒤 축소, 힌트 여백.
3. `web/src/styles/base.css`: 예습 퀴즈 `.quiz-hint summary` 모양을 `.quiz-hint-toggle` 버튼에도 적용(선택자 추가만).
4. `web/tests/root-photo-quiz.{html,tsx}`: 큰 사진 1·2장 고정물.

## 검사

- `web/`에서 `npx tsc -b`.
- vite 고정물 `tests/root-photo-quiz.html`(?images=2, ?stay=1)을 1280×800·1366×650·375×812에서.

## 위험·복원

- 위험 낮음: 화면 CSS·마크업만. 복원은 `git revert`.
