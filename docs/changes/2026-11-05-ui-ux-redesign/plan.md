# UI/UX 개편: 좌측 메뉴·흰색 바탕·캘린더 — 구현 계획

브랜치 `claude/ui-ux-redesign-727bb1`(origin/master `a3f67d1` 기준, 업스트림 없음). 대시보드 행 등록 완료(dashboard `5f4b14e`).

## 결정(2026-11-06 사용자 답변)

1. 갈래 색: **5조합으로 대체.** 2026-08-31 `--fam-*` 고정 지시를 사용자 선택 5조합(복습 = 메인, 예습 = 두 번째)으로 바꾼다.
2. 서버 저장: **2단계로 분리.** 1단계는 웹만 배포한다. 강의록 회독 +/삭제와 자유 노트 메뉴는 서버 저장(새 표·API, 운영 DB 승인)과 함께 2단계에서 연다.
   1단계 회독 줄은 예습 퀴즈 완료 토막만 표시한다(기존 데이터로 계산).
3. 없는 메뉴: **기능이 생길 때까지 숨김.** 1단계 메뉴: 캘린더·강의 목록 / 공지사항 / 이용방법·문의하기·(관리자)관리 / 프로필.
4. 블럭 분리: **감염과 면역만 분리.** 일반 규칙은 그대로 두고 이 과목만 1차 시험에서 「감염과 면역 1차」·「2차」로 나눈다.

## 변경 범위·대상 파일·순서

1단계 — web만(결정 1·3·4 반영, 자유 노트·강의록 회독 제외). 각 단계마다 `npm run typecheck`.
1. 토큰·테마: `src/styles/base.css`(새 회색·강조 토큰, `--exam`, 다크 값), 새 `src/theme.ts`(5조합·localStorage·적용).
2. 앱 틀: `src/App.tsx`, 새 `src/shell/Sidebar.tsx`·`sidebar.css`, `src/StudyNav.tsx`(풀이 화면 유지 확인). 새 `src/settings/SettingsPage.tsx`.
3. 갈래·번호·블럭: 새 `src/calendar/kinds.ts`(표시 갈래·번호), `src/bank/studyBlocks.ts`(감염과 면역 1차 시험 분리 예외), `src/calendar/entries.ts`(표시 필드 연결).
4. 캘린더: `CalendarPage.tsx`(머리 D-day·「오늘」 줄·도구 위치·학습 자동 로딩), `CalendarGrid.tsx`(점심 얇은 줄), `EventChip.tsx`·`ChipLearning.tsx`
   (번호·교수 표시·회독 점선·복습 막대), `ProfessorInfo.tsx`(연도/N 표시), `useCalendarTimetable.ts`, `styles/calendar.css`.
5. 패널: `EventPanel.tsx`(구성 재배치·관리자 접힘), `PreviewAction.tsx`·`ReviewAction.tsx`(짧은 버튼 모양, 동작 불변), `panelShared.tsx`.
   `bank/BankPanel.tsx`는 import 목록을 바꾸지 않는다(`bank-links.test` 허용 목록).
6. 강의 목록: `bank/StudyOverview.tsx`·`overview.css`·`BankBatch.tsx`(갈래 묶음 표·단계 색·저장·선택 막대·더 보기 접힘).
7. 이용방법: `notices/GuidePage.tsx`.
8. 테스트 갱신: `web/tests/professor-preview.*`, `calendar-loading.*`, `study-blocks.test.cjs`, `study-loading.test.cjs`, `study-management.*`,
   `preview-actions.test.cjs`, 시각 고정물(`calendar-learning.tsx` 등)을 새 마크업·문구에 맞춘다. 단언 의미(요청 형태·지연 로딩·가로 넘침 없음)는 유지.

2단계 — 결정 2 승인 시: `server/app/models/`(note_read, user_note), `server/app/routes/me.py` 또는 새 `notes.py`, `server/app/cli.py`(호환 생성),
`server/tests/`(새 라우트·소유권·route_contract), 웹 `src/notes/*`(프로토타입 편집기 이식), 패널 회독 +/삭제/되돌리기 연결.

## 검사 명령과 성공 조건
- web: `npm run typecheck`, `npm run build` 통과. CI와 같은 `node --test web/tests/wait-for-api.test.mjs`.
- 수동 Playwright 검사(로컬 vite 고정물, 운영 API 미사용): `node web/tests/run-professor-preview.cjs --all`, 위 8의 각 `node --test web/tests/<이름>.test.cjs`.
- 브라우저 확인: 데스크톱 1280·1600, 태블릿 900, 휴대폰 390에서 캘린더·패널·강의 목록·설정·이용방법, 가로 넘침 없음, 콘솔 오류 없음.
- 2단계: `server/.venv/Scripts/python.exe -m tests note`, `-m tests route_contract`, 격리 로컬 DB만 사용(`server/.env` 운영 DB 금지).
- 각 체크는 `python scripts/development.py verify 2026-11-05-ui-ux-redesign --check web -- <명령>`으로 기록.

## 위험·복원·승인할 범위
- 위험: 패널·목록 마크업 변경으로 기존 UI 테스트 대량 수정 → 단언 의미를 유지한 채 선택자만 바꾼다. 확장 링크 수신·지연 로딩·URL 상태 회귀 → 해당 테스트로 확인.
  학습 정보 자동 로딩으로 요청 수 증가 → 첫 화면 요청은 그대로, 그 뒤 기존 학습 요청을 자동 실행(카드 단계는 목록·패널에서만).
- 팀원 작업과의 겹침: 대시보드의 출제·Map·뿌리 작업은 파일이 겹치지 않는다. 뿌리·연결 학습 진입(BankStart·BankStudy)은 그대로 둔다.
  `RootOverviewPanel`은 강의 목록 「더 보기」 안으로 옮기기만 한다.
- 배포: master merge 시 자동 배포. PR·CI 통과·사용자 확인 후에만 merge한다. 2단계는 DB 준비(새 표·RLS) → API → 웹 순서, 중요 운영 승인 후.
- 복원: 웹은 Pages 이전 배포 Rollback 또는 `git revert` PR. 1단계는 데이터 변경이 없다. 2단계 표는 지우지 않고 웹 진입만 되돌린다.
- 승인할 범위: 위 1단계 파일·기능의 로컬 구현과 검사, PR 생성까지. merge·운영 배포·DB 변경은 별도 확인.
