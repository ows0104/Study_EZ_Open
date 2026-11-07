# UI/UX 개편: 좌측 메뉴·흰색 바탕·캘린더 — 배포 준비

1단계(웹만) 로컬 구현·검사 결과. 브랜치 `claude/ui-ux-redesign-727bb1`(origin/master `a3f67d1` 기준). 아직 커밋·PR·배포 전.

## 코드 리뷰·검증 결과

구현 범위(plan.md 1단계, 2026-11-06 구현 승인):
- 앱 틀: 상단 `app-bar` → 좌측 메뉴(`src/shell/Sidebar.tsx`), 설정 화면(`src/settings/SettingsPage.tsx`), 색 5조합(`src/theme.ts`).
  풀이 화면(bare)과 `StudyNav`는 유지. 피드백은 좌측 「문의하기」로.
- 토큰(`styles/base.css`): 회색 단계·강조 2색·`--exam`. `--fam-*` 고정색은 사용자 결정 1로 강조색에 연결.
- 표시 갈래·번호·블럭(`calendar/kinds.ts`, `bank/studyBlocks.ts`): DB 불변. 실제 2026 2학기 시간표로 확인 —
  감염과 면역 1차 강의 1–46, 2차 1–18, TBL n 영상, CBL 1–9, 11-05 기본 블럭 「1차」·11-24 「2차」.
- 캘린더(`CalendarPage`, `EventChip`, `ChipLearning`, `useTodayDue`): D-day, 「오늘」 줄, 회독 점선·복습 막대 항상 표시.
- 패널(`EventPanel`, `PreviewAction`·`ReviewAction` 이름·자리만): 짧은 버튼, 통계, 덱 다운로드, 관리자 접힘.
  출처 변경 안내(`PreviewSourceNotice`)는 web/CLAUDE.md 계약대로 학생 패널에 유지.
- 강의 목록(`bank/StudyOverview.tsx`·`overview.css`, 하위 에이전트 구현 후 검토): 갈래 묶음 표·단계 색·저장·선택 막대,
  숨기기·관리자 삭제·약리학 준비 칸·시험 계획·뿌리 개요는 「더 보기」로 이동(동작 불변).
- 이용방법(`notices/GuidePage.tsx`) 문구 갱신.

검사(state.json `checks`, 로그 `runs/_development/2026-11-05-ui-ux-redesign/`):
- `tsc -b web/tsconfig.json --noEmit` 0
- `node web/tests/run-professor-preview.cjs --all` 0 (캘린더 4개 통과)
- `node --test web/tests/preview-actions.test.cjs web/tests/wait-for-api.test.mjs web/tests/firstScreen.test.cjs` 0
- `cmd /c npm --prefix web run build` 0 (web_artifact 기록). 같은 날 앞선 `cmd C:/ npm …` 기록은 셸 경로 변환으로
  빌드를 실행하지 않은 무효 기록이다(exit 0이지만 근거로 쓰지 않는다).
- 수동 실행(5197 고정물 서버, verify 기록 없음): study-blocks·study-loading·study-management 16/16 통과,
  shared-preview-prompt 2/2 통과, quiz-publication 2/3 통과.

기존 결함(이번 변경 전부터, 이번 브랜치에서 관련 파일 미변경):
- `quiz-publication` 「missing current link…」: 고정물의 옛 텍스트 프롬프트가 PR #6의 JSON 프롬프트 검증에서
  「출제 프롬프트 파일이 올바르지 않습니다」로 막힌다(`bank/prompt.ts`, `QuizCreateButton.tsx` 미변경).
- `bank-links.test.cjs`: `BankPanel.tsx`의 `./RootGenerationPanel` import가 테스트 허용 목록에 없다(둘 다 미변경).

검토에서 고친 것: 시험 세부 「(1차)」가 칸 세부에서 빠져 D-day 이름이 「시험」이 되던 것, 오래된 컨테이너 규칙이 낮은 칸의
교수 줄을 숨기던 것, 여러 시간 칸의 내용이 세로 가운데로 가던 것, 학생 패널에서 출처 변경 안내가 빠졌던 것,
강의 목록 제목에 분야 머리가 남던 것, 빌드가 다시 쓴 `web/public/bank-prompt.json`(줄바꿈만, 팀원 영역)을 되돌림.

남은 위험: 캘린더가 첫 그림 뒤 보이는 범위 학습률 1건 + 오늘 복습 수(현재 블럭 강의 8개씩)를 자동으로 더 부른다.
강의 패널은 열 때 그 강의 하나의 study-progress를 부른다. 학생에게 덱(`pre_apkg`·`main_apkg`) 다운로드 링크가 새로 보인다
(서버는 원래 승인 사용자에게 서명 허용).

### 2026-11-07 추가 반영(PR #9 두 번째 커밋)
사용자 「Yes, apply」(intent.md 2026-11-07 (1)–(6)):
- 캘린더 머리: 「감염과 면역 1차 1주차 D-13」 한 줄 + 오른쪽 끝 오늘 예습·복습 카드(좁은 화면·패널 열림 시 아래 줄).
  오늘 버튼·주/월·월간 보기·「덱 모아받기 보기」(관리자 포함) 제거, 날짜 줄 양끝 ‹ ›로 주 넘기기. 관리자 블럭 덱은 패널 「관리자」에 남음.
- 스크롤 없는 격자: 좌측 메뉴 기준 높이(`calc(100dvh - 68px)`, 태블릿·휴대폰 별도), 줄 최소 40px. 1440×900·1280×720 고정물에서 격자·페이지 스크롤 없음.
- 시험 칸: 옅은 빨강 + 「감염과 면역 1차 시험」(앞 7일 수업의 블럭 이름, `kinds.ts`).
- 빈 막대: 5px, 채움 없이 1px 테두리(예습 미완료·복습 미개방). 예습 완료 토막 72% 맑은 색.
- N 규칙(`professorNote`): 작년과 다르고 같은 교수 필기가 없으면 needs_review여도 N(러너가 newProfessor를 비우는 경우).
- 개인 대화 C안(`ChatSplit.tsx`): 왼쪽은 처음 만들기(＋)·이후 열기(↗), ▾에 새 대화 만들기·내 프롬프트 수정. 대화 버튼 갈래 색, 모든 버튼 34px.
- 이용방법 문구와 테스트(calendar-loading·professor-preview·preview-actions·shared-preview-prompt) 갱신.
검사(기록): tsc 0, run-professor-preview --all 0(4/4), preview-actions·wait-for-api·firstScreen 0(28), build 0. 수동: shared-preview-prompt 2/2.
남은 것: 「강의별 보기의 퀴즈 탭」 스크롤은 대상 화면 확인 전이라 미반영. 강의록 회독의 「앞에서부터 채우기」는 2단계(회독 저장)와 함께.

## 배포 대상 버전·순서·데이터 변경
- 웹만. 서버·DB·러너·확장 변경 없음. master 병합 시 자동 배포(API 같은 SHA 확인 후 Pages).
- 프로토타입(`web/src/redesign-prototype/`, `web/redesign-prototype.html`, `vite.prototype.config.ts`)과 확인용 고정물
  (`web/tests/redesign-shell.*`)은 운영 빌드 입력이 아니다(tsc 대상이라 타입 오류는 막는다).
- 2단계(강의록 회독 저장·자유 노트)는 새 표·API와 운영 DB 승인이 필요하며 이번 범위가 아니다.

## 배포 후 확인·롤백·필요한 사람 승인
- 커밋·PR 생성, master 병합(=운영 배포)은 사용자 확인 후.
- 배포 후: Pages 같은 SHA, 캘린더·패널·강의 목록·설정·이용방법을 데스크톱·휴대폰에서 읽기 전용 확인, 콘솔 오류 없음.
- 롤백: Pages 이전 배포 Rollback 또는 `git revert` PR. 데이터 변경이 없어 되돌릴 기록 없음.
  사용자 기기의 localStorage(`studyez-accent`, `studyez-sidebar`)는 남아도 무해하다.
