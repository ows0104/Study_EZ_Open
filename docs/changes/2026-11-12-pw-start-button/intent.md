# Main-Quiz Playwright 시작 버튼 찾기 수정

## 문제와 사용자 효과
`web/tests/root-learning.test.cjs`의 4개 테스트(actual API, toggles, Z undo, quiz timer)가 master에서 실패한다.
「오늘 학습 시작」 버튼에 카드 수 표시(`aria-label="카드 N개"`)가 붙어 접근성 이름이 「오늘 학습 시작 카드 N개」가 되었는데,
네 곳만 `exact:true`로 찾아 시간 초과한다. 화면 동작 결함이 아니라 검사 결함이다. CI에서 Main-Quiz UI 회귀를 놓치게 된다.

## 범위와 성공 기준
- 테스트의 네 줄만 다른 줄들과 같은 부분 일치로 바꾼다. 화면 코드 변경 없음.
- 격리 fixture에서 8개 테스트 전부 통과.

## 근거·미정 사항
- 사용자 지시(2026-11-12): 「이 작업을 여기에서 진행해 주세요: “Fix 4 failing Main-Quiz Playwright tests”」.
- 원인 확인: PR #138 작업 중 master 웹 코드로 같은 fixture를 돌려 같은 4개가 같은 이유로 실패함을 확인.
