# 캘린더 오늘 복습에 오늘 푼 문제 수 — 구현 계획

## 변경 범위·대상 파일·순서
1. `web/src/calendar/CalendarPage.tsx` `ReviewCard`: 「푼 문제 n」.
2. `web/src/styles/calendar.css` `.today-card-solved` 한 줄(오늘 할 일 칸 블록. review-bar-soft-fill의 끝 막대 블록과 다른 자리).
3. `web/src/notices/GuidePage.tsx` 66행(choices-collapse와 같은 파일, 다른 절).
4. `docs/changes/2026-11-13-daily-goal-questions/handoff.md`.

## 검사 명령과 성공 조건
- `npm --prefix web run typecheck`, `build` 통과.
- 고정 응답으로 칸 3상태(진행 중·완료·계획 없음) 화면 확인.

## 위험·복원·승인할 범위
웹만. 병합(=배포)은 사용자 승인. 복원은 병합 커밋 revert.
