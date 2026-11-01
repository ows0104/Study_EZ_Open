# 블록 자동 전환 — Implementation Plan

## 변경 범위·순서
1. studyBlocks.ts와 useStudyCourse.ts에 시간표 기반 선택과 시각/선택 상태를 구현한다.
2. StudyOverview.tsx에서 준비 상태 기반 초기 선택을 교체하고, 첨부 없는 예정 수업도 블록 이름으로 묶는다.
3. calendar/entries.ts 주석과 GuidePage.tsx, web/CLAUDE.md에 토/일요일 및 시험 종료 전환 규칙을 명시한다.
4. web/tests/study-blocks.test.cjs에서 시험 전/후 경계·중간/마지막 시험·실습 꼬리·겹치는 과목·준비 전 수업·빈 표·실제 시간표·시간대·주말과 선택 상태 갱신을 검증한다. 실제 StudyOverview의 최초 렌더도 확인한다. study-block-transition.html/tsx와 check_browser.py는 별도 로컬 브라우저에서 목록 도착·수동 선택 유지·시험 종료·주기 갱신·탭 복귀를 검증한다.
5. revision-bound 검사, 코드 리뷰와 release.md를 기록한다. 이번에는 운영 배포하지 않는다.

## 검증
block-selection: node --test web/tests/study-blocks.test.cjs
browser: 로컬 Vite 검사 서버를 실행한 뒤 server/.venv/Scripts/python.exe -X utf8 docs/changes/2026-11-01-block-auto-selection/check_browser.py (실제 계정/API 없는 격리 브라우저)
web: npm.cmd --prefix web run typecheck 후 npm.cmd --prefix web run build. 각 실제 명령을 development.py verify로 기록한다(typecheck는 별도 check).

## 승인과 복원
현재 사용자의 명시적 “고쳐줘”와 주간 기준 확인을 위 기능의 로컬 구현·검증 승인으로 기록한다. 이전 조사만으로는 구현하지 않았고 현재 승인을 적용한다. 변경 파일만 검토하며 다른 작업의 미커밋 변경은 보존한다. 복원은 이번 파일/변경만 되돌리고 운영 데이터는 건드리지 않는다. 운영 배포는 후보와 중요 승인이 필요한 별도 단계다.
