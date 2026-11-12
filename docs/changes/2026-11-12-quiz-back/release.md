# 퀴즈 풀이 중 뒤로가기 — 검증

- `npm run build` 통과(tsc·vite).
- Main-Quiz(격리 fixture, 운영 DB 미사용): 시작 → 1문항 답 보기·평가 → 「뒤로」 → 시작 화면에 첫 학습 1/3, 「오늘 학습 재개」 표시. 기록 유지 확인.
- Pre-Quiz(메모리 대체 API): 1문항 이해 확인 → `/check` 1회 저장 확인 → 「뒤로」 → 풀이 화면을 떠남.
  테스트 페이지는 MemoryRouter라 홈(`/`) 분기만 확인. 실제 앱의 history back 분기(react-router 7 `history.state.idx`)는 브라우저 미확인.
- 미실행: Playwright `web/tests/root-learning.test.cjs`(전용 fixture 구성). CI `Tests and build`가 실행한다.
