# 강의 패널 개념 지도 버튼·지도 좌측 상단 뒤로 — 구현 계획

## 변경 범위·대상 파일·순서
1. web/src/links.ts — mapHref.
2. web/src/calendar/EventPanel.tsx — 복습 줄 trailing만.
3. web/src/bank/RootLearning.tsx — ?map=1 진입·뒤로.
4. web/src/bank/RootMap.tsx, web/src/bank/main-quiz.css — 뒤로 버튼 위치.

## 검사 명령과 성공 조건
- `npm --prefix web run typecheck` 통과.
- 가짜 API 고정물(커밋하지 않음)로 `?map=1` 진입 시 지도가 바로 열리고 좌측 상단 「뒤로」가 지도를 떠나는지, 375px에서 겹치지 않는지 확인.

## 위험·복원·승인할 범위
- 웹만. 되돌리기는 커밋 revert. EventPanel.tsx는 족보 회독 작업과 같은 파일 다른 블록(사용자 확인).
