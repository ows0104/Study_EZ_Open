# 이용현황 자료 첨부 칸 정리와 빠진 행동 기록 — 구현 계획

## 변경 범위·대상 파일·순서
1. server/app/models/previews.py — `PREVIEW_ACTION_KINDS`에 screate·rcreate·rmine.
2. server/app/usage_actions.py — 칸·행동 이름, 새 행동 9개 등록.
3. server/app/routes/usage.py — `ROOT_KINDS`·`PREVIEW_FIELDS`로 root_event·preview_open 갈래 연결, `user_review` 요약·상세·마지막 활동.
4. server/tests/test_usage_actions.py — 새 갈래 분리·복습 링크 저장·Main-Quiz 갈래·「미상」 이름 없음 검사.
5. web/src/usage.ts(kind 타입), web/src/calendar/PreviewAction.tsx(screate), ReviewAction.tsx(rcreate·rmine), web/src/admin/UsageTab.tsx(설명 문구).
6. docs/development/usage-actions.md — 현재 세는 것·안 세는 것 목록.

## 검사 명령과 성공 조건
- server: `.venv/Scripts/python.exe -m tests usage`(usage·usage_actions·file_request_purpose 3개), `-m tests file_request`, `-m tests route_contract`, `-m tests smoke` 전부 통과.
- web: `npm run typecheck`, `npm run build` 통과, `node --test tests/preview-actions.test.cjs` 통과.
- 브라우저: tests/review-actions.html에서 공통·개인 예습, 복습 만들기 클릭 시 screate·create·rcreate가 각각 한 번 기록되는지.

## 위험·복원·승인할 범위
- 위험: 서버보다 웹이 먼저 나가면 새 kind는 서버가 조용히 버린다(기록 누락뿐, 화면 오류 없음). master 병합은 API→웹 순서로 자동 배포된다.
- 복원: git revert. 새로 쌓인 screate·rcreate·rmine 행은 옛 코드가 무시하므로 지울 필요 없다.
- 승인: 사용자 작업 요청(intent.md 원문)이 구현 승인이다. 아직 안 세는 행동을 더할지는 따로 묻는다.
