# 캘린더 복습 막대 색 옅게 — 구현 계획

## 변경 범위·대상 파일·순서
1. web/src/styles/calendar.css — `.meter`, `.readline i.rl-pre.is-on`
2. web/src/calendar/ChipLearning.tsx — `reviewFill` 추가, `ReviewMeter`가 사용
3. web/src/calendar/CalendarPage.tsx — 범례 표본이 `reviewFill(25)` 사용

## 검사 명령과 성공 조건
- web: `npm run typecheck`(tsc) 오류 없음, PR의 `Tests and build` 통과.
- 화면: web/tests/calendar-learning.html 고정물에서 막대 바탕이 「오늘 복습」 박스 바탕과 계산값이 같고
  채움이 바탕과 구분됨(2026-11-12 로컬 확인).

## 위험·복원·승인할 범위
표시만 바뀐다. 되돌리기는 git revert. 승인 범위는 위 세 파일과 이 기록.
