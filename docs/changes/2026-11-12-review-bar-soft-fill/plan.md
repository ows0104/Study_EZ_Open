# 캘린더 복습 막대 채움을 연한 강조색으로 — 구현 계획

## 변경 범위·대상 파일·순서
1. web/src/styles/calendar.css — `.meter > span` 채움 색 한 줄과 사용자 지시 주석
2. web/src/calendar/ChipLearning.tsx — 주석의 「메인 색」을 「연한 메인 색」으로

## 검사 명령과 성공 조건
- web: `tsc -p web --noEmit` 오류 없음, PR의 `Tests and build` 통과.
- 화면: web/tests/calendar-learning.html 고정물에서 채움이 연한 메인 색, 테두리 회색 그대로.

## 위험·복원·승인할 범위
표시만 바뀐다. 되돌리기는 git revert. 승인 범위는 위 두 파일과 이 기록.
