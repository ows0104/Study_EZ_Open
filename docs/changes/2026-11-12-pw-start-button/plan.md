# Main-Quiz Playwright 시작 버튼 찾기 수정 — 구현 계획

승인: 사용자 지시(2026-11-12) 「이 작업을 여기에서 진행해 주세요」.

## 변경 범위·대상 파일·순서
1. `web/tests/root-learning.test.cjs`: 네 줄의 `exact:true` 제거.

## 검사 명령과 성공 조건
- 격리 fixture API(`tests.serve_main_quiz_ui_fixture`, 8027) + vite(5193)에서 `node --test tests/root-learning.test.cjs` 8개 통과.

## 위험·복원·승인할 범위
- 위험 없음(테스트만). 복원은 `git revert`.
