# 화면 토글을 한 번 누른 값으로 기억 — 구현 계획

## 변경 범위·대상 파일·순서
1. `web/src/preferences.ts`(새): usePreference.
2. `web/src/shell/Sidebar.tsx`, `web/src/bank/StudyOverview.tsx`: 기존 저장 코드를 도우미로(같은 키).
3. `web/src/bank/RootMap.tsx`: allOpen·showAll. `web/src/admin/BankReportTab.tsx`·`CardReviewTab.tsx`: showDone.
4. `web/tests/preferences.test.cjs`(새): 저장·복원·허용값 외 무시·저장소 차단 시 fallback.

## 검사 명령과 성공 조건
- `web`에서 typecheck·build, 새 검사, `scripts/check_main_quiz_ui.py browser`(격리 fixture, 개념 지도 포함) 통과.

## 위험·복원·승인할 범위
- 화면 설정만 바뀐다. 복원은 커밋 되돌리기. 서버·DB 변경 없음.
- 승인 범위: 위 파일의 화면 변경과 로컬 검사.
