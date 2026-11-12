# 좁은 화면 글씨 줄바꿈 — 구현 계획

## 변경 범위·대상 파일·순서

1. 새 파일 `web/src/styles/responsive.css`(R1·R2·R3).
2. `web/src/main.tsx`에서 calendar.css 다음에 import 한 줄.

기존 css·tsx는 고치지 않는다(claude/review-bar-ux와 겹침 조정).

## 검사 명령과 성공 조건

- `npm run typecheck`, `npm run build` 통과.
- 로컬 local-test API(격리 SQLite, 시간표만 seed) + vite에서 375·700·1280px로 잘린 글자 측정
  (scrollWidth/scrollHeight가 상자보다 큰 요소 목록). 375px 캘린더 칸은 제목 세 줄 + 교수,
  강의 목록은 강의명 전체, 700px 캘린더 머리 제목 전체, 1280px는 전과 같음.

## 위험·복원·승인할 범위

위험: 칸 높이를 손으로 잰 값(63.8px)에 맞췄다. 칸 높이가 바뀌면 세 줄 조건이 꺼질 뿐 넘치지는
않는다(조건이 min-height). 복원은 import 한 줄을 지우면 된다.
승인: 사용자 2026-11-12 요청이 구현 승인이다. 배포는 master 병합 시 자동.
