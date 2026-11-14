# 검증

- `npx tsc -b --noEmit` 통과, `npm run build` 통과, `tests/jokbo-selection.test.cjs` 통과.
- vite(5216, 운영 DB·API 미사용) 고정물 `tests/jokbo-undo.html` 브라우저 실행: 20/20 ALL PASSED
  (평가 전 z 무시·답만 본 문제 z 무시·직전 문제 답 화면 복귀·표시 복원 high·채점 재기록 없음·두 번째 z 대기·Ctrl+Z·끝 화면 z·회독 1회 유지).
- 미확인: 운영 족보 화면에서의 손 조작.
