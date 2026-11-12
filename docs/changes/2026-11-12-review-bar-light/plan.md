# 캘린더 복습 막대: 테두리 + 강조색 채움 — 구현 계획

## 변경 범위·대상 파일·순서
1. web/src/styles/calendar.css — `.meter`, `.readline i.rl-pre`, `.readline i.rl-pre.is-on`
2. web/src/calendar/ChipLearning.tsx — 인라인 채움 색 제거, 머리 설명 갱신
3. web/src/calendar/CalendarPage.tsx — 범례 표본 인라인 색 제거

## 검사 명령과 성공 조건
- web: `tsc -b web --noEmit` 오류 없음, PR의 `Tests and build` 통과.
- 화면: web/tests/calendar-learning.html 고정물에서 막대 바탕 투명·회색 테두리·메인 색 채움, 예습 토막 미완료 회색 테두리/완료 채움.

## 위험·복원·승인할 범위
표시만 바뀐다. 되돌리기는 git revert. 승인 범위는 위 세 파일과 이 기록.
