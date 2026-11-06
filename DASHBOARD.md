# StudyEZ 작업 대시보드

> 이 파일은 `dashboard` 브랜치에만 있다. master에 merge하지 않는다.
> 작업 전에 반드시 `git pull`로 최신 상태를 받고, 확인 → 내 작업 작성 → push 후 작업을 시작한다.
> 규칙 전문: master의 `docs/development/collaboration.md` "작업 시작 대원칙".

우선순위: **P0** 긴급(운영 장애·데이터 위험) · **P1** 이번 주 · **P2** 다음 · **P3** 언젠가

---

## 1. 지금 하고 있는 작업

같은 영역·파일이 다른 행과 겹치면 시작하기 전에 상대와 조정한다.

| 우선순위 | 작업 | 작업자 / 세션 | 브랜치 | 건드리는 영역·파일 | 시작일 | 상태·메모 |
|---|---|---|---|---|---|---|

| P1 | Map·독립 출제포인트 추출 프롬프트 정리 | ows0104 / Codex Map 세션 | codex/map-point-prompts | content/prompts/learning-links/map-extract.md, point-extract.md, *-output.schema.json, *-output.example.json, README.md, docs/changes/2026-11-06-map-point-prompts, .worktrees/map-point-prompts/runs/_map-point-pilot | 2026-11-06 | 사용자 승인 범위의 두 원본 전용 지시문·JSON 스키마·예시·로컬 형식 검증. 현재 사용자 예시 추출 승인: 명시적 OpenAI 전송 승인으로 Map/포인트 각1회 완료, 심내막염·CNS 강의별 JSON4개 보존. 후속 승인된 독립단위 재추출·4지적 보완·별도 재대조 완료: 최종47/60개, ready/ready·잔여issues없음. 원본/중간/실패보존, 필수검사통과, d68b6d57 로컬 검토대기. 운영 요청 재개/문항/게시/배포 없음 |

| P1 | Map 흐름 예시를 반영한 별도 프롬프트 복사본 | ows0104 / Codex Map 참고 세션 | codex/map-flow-reference | content/prompts/learning-links/map-extract-reference.md, docs/changes/2026-11-06-map-flow-reference, .worktrees/map-flow-reference/runs/_map-flow-experiment | 2026-11-06 | 별도 짧은 지시문 실험 완료: 심내막염20개념/25연결·CNS24개념/31연결, 단일 호출296초. 원본/형식검증·PNG확인. 기존시범/운영미변경. 로컬브랜치 검토대기 |

| P1 | 심내막염·CNS Map→포인트→문제→실제 풀이 E2E 실험 | ows0104 / Codex E2E 세션 | codex/map-point-e2e | docs/changes/2026-11-06-map-point-e2e, runs/_e2e/26110507 (실험 전용 저장소·격리 DB·로컬 앱), 기존 추출 결과 읽기 전용 | 2026-11-06 | CNS49문항 중40과제 실제UI·응답/진도 새로고침 복원·별도 기술계정 사건 저장 확인. 사람기록0 유지해 풀이 링크/JSON 제공. 심내막염47문항 최종 source-2/medical-2 완료했으나 서로 다른 C001/C012 중복으로 BANK등록 실패·3회상한 도달 보류(40ok/6doubt/1wrong). 양강의 완료 아님. 원본740파일·실패/소비보존, 운영548/DB/은행/학습/배포변경없음. 로컬 검토대기 |

| P1 | 완료 작성 초안의 구조 수용 실패 복구 | ows0104 / Codex E2E 복구 세션 | codex/root-authoring-recovery | quizbank/connection_generate_v2.py, quizbank/connection_authoring_recovery.py, studyez_contracts/roots/generation_v2.py, runner/root_native_json.py, 관련 tests, docs/changes/2026-11-06-root-authoring-recovery | 2026-11-06 | de1fcf73 구조복구·252검사+서버3·실제740파일보존/복구증거 통과. CNS49/40 준비. 심내막염 후속은 별도 root-tier-transport 후보로 연결, 최종ID중복 보류. 원래실패·3회상한 보존. 로컬 검토대기·운영미배포 |

| P1 | UI/UX 개편: 좌측 메뉴·흰 바탕·캘린더·강의 목록(학습 현황+모아풀기 통합)·강의 패널·회독·자유 노트를 운영 웹에 적용 | HungryPotato01 / Claude UI 개편 세션 | claude/ui-ux-redesign-727bb1 | web/src/App.tsx·셸, web/src/calendar/*, web/src/styles/*, web/src/bank/StudyOverview.tsx·overview.css(목록 화면), web/src/bundle/*, web/src/notices/GuidePage.tsx, 새 web/src/notes/*; 회독 기록이 서버 저장이 필요하면 server 학습 기록 API·테이블(별도 승인 후). 프로토타입 web/src/redesign-prototype/*, docs/changes/2026-11-05-ui-ux-redesign | 2026-11-06 | 2026-11-06 1단계(웹만) 구현 승인·로컬 구현·검사 완료, PR [#9](https://github.com/ows0104/Study_EZ_Open/pull/9) 검토·CI 중(병합=운영 배포, 사용자 확인 후). 2단계(회독 저장·자유 노트, 새 표·API)는 별도 승인. 출제·quizbank·studyez_contracts/roots·runner·content/prompts는 건드리지 않는다. 겹침 확인 필요: 뿌리·연결 학습 진입(BankStart·BankStudy)은 그대로, 강의 목록의 뿌리 개요는 「더 보기」 안으로 옮김(동작 불변). 추가로 web/src/shell·settings·theme.ts, calendar/kinds.ts 새 파일. 사용자 조정: Main Quiz 시작/풀이/생성·학습 API는 Codex main-quiz-unified가 담당, 이 세션은 메뉴/캘린더/목록/이용안내 담당. 2026-11-06 사용자 재조정: codex/admin-main-quiz-one-click가 Main Quiz 버튼·중복 패널 정리 담당, calendar/셸 변경 제외 |

| P1 | E2E 완료 파일의 기존 등급 별칭 전송 복구 | ows0104 / Codex E2E 형식 복구 세션 | codex/root-tier-transport | studyez_contracts/bank/authored_json.py, roots/generation_v2.py, runner/root_native_json.py, runner/root_tier_recovery.py, quizbank/connection_generate_v2.py, 관련 tests, docs/changes/2026-11-06-root-tier-transport | 2026-11-06 | bba2dad6 기존별칭1곳 및 파생설명순서 호환·명시지문재검증, 모델재호출0·소비3 유지. 12전용+252회귀+서버3·실제Native/보존검증통과. 최종source-2/medical-2 완료. 다른 C001/C012 중복은 임의합치지 않고 BANK등록보류. 코드 기술복구와 콘텐츠수용 구별. 로컬 검토대기·운영미배포 |



| P1 | 관리자 Main Quiz 원클릭 생성·검수·업로드와 중복 패널 정리 | ows0104 / Codex Main Quiz 버튼 세션 | codex/admin-main-quiz-one-click | web/src/bank/BankPanel.tsx, RootGenerationPanel.tsx, rootWeb.ts, 관련 web/tests, docs/changes/2026-11-06-admin-main-quiz-one-click | 2026-11-06 | 사용자 조정 승인: Main Quiz만 담당, Claude UI 세션의 메뉴/캘린더/목록은 제외. 문제은행 웹 작성, 원본 지도·포인트 CLI 추출, CLI 통합·검수, 러너 업로드. 기존 기록·상한 보존 |

## 2. 앞으로 하기로 약속된 일


| 우선순위 | 작업 | 예정 작업자 | 예상 영역·파일 | 선행 조건·메모 |
|---|---|---|---|---|
| | | | | |

## 3. 제안된 아이디어 (논의 필요)

합의되면 2번으로 옮긴다. 합의 전에는 구현을 시작하지 않는다.

| 아이디어 | 제안자 | 제안일 | 논의 내용·결정 |
|---|---|---|---|
| | | | |

---

## 완료 기록 (최근 것만)

merge가 끝나면 1번에서 지우고 여기에 한 줄 남긴다. 오래된 줄은 지워도 된다.

| 완료일 | 작업 | 작업자 | PR |
|---|---|---|---|
| 2026-11-06 | 새 파이프라인의 Main Quiz 통합(회상 단위 PR7 포함) 7b96003f master 반영. 필수 계약644·서버52·웹27·CUA15 통과. API·Pages7b96003f 같은SHA 배포 및 실제 Main Quiz assets 대조 완료(한국15:16:51 게시). [배포 기록](https://github.com/ows0104/Study_EZ_Open/blob/codex/main-quiz-unified/docs/changes/2026-11-06-main-quiz-unified/deployment.md). 직접 게시 준비는 자동복구로 종료·수동 업로드0. GuidePage 인계: 새 화면 Space/Enter 답 확인·1/2/3 회상평가·Z 취소, 기존 은행4등급/기록 유지 | ows0104 / Codex Main Quiz 세션 | [#8](https://github.com/ows0104/Study_EZ_Open/pull/8) |
| 2026-11-05 | 순수 JSON 수신·검증·결정적 변환과 프롬프트 1.82 API·웹 a3f67d13 배포 완료. 전체 검사/health SHA/401/운영 프롬프트 확인. 로컬 러너 코드 갱신·기존 매칭 보존. 브리지 1.3.23 사용자 업데이트 필요 — [배포 기록](https://github.com/ows0104/Study_EZ_Open/blob/codex/bank-json-delivery/docs/changes/2026-11-05-bank-json-delivery/deployment.md) | ows0104 / Codex JSON 전환 세션 | [#6](https://github.com/ows0104/Study_EZ_Open/pull/6) |
| 2026-11-05 | 교수별 예습·CBL 매핑과 적용 기록 master 반영 및 API·웹 `5c56d462` 배포 완료. 양쪽 전체 검사/health/401/Pages success/CBL 세 첨부 유지 확인 — [배포 기록](https://github.com/ows0104/Study_EZ_Open/blob/04e60a2df003dcb7688e3678457754a13d506577/docs/changes/2026-11-05-cbl-prev-notes/repository-deployment.md) | ows0104 / Codex 교수별 예습 세션 | [#5](https://github.com/ows0104/Study_EZ_Open/pull/5) |
| 2026-11-05 | 미정 CBL 3개에 주제와 관련 CBL 기출을 확인한 2025년 필기 연결 완료. 세 PDF 실제 해시/학습 기록 보존/운영 화면 확인 및 러너 복원. 코드 재배포 없음 — [운영 기록](https://github.com/ows0104/Study_EZ_Open/blob/2d420b1f78f670f0dfa205bd0b86917bc7b0f675/docs/changes/2026-11-05-cbl-prev-notes/deployment.md) | ows0104 / Codex 교수별 예습 세션 | 승인된 자료 연결, 기록 codex/cbl-prev-notes |
| 2026-11-05 | 교수 변경·신규 교수 표시 및 최근 5년 동일 교수 최신 필기 우선, 없으면 작년 대체 운영 반영 (`c86e15fb`). 84개 강의·기록 보존, PDF 72개 실제 검증, 러너 복원 완료 — [배포 기록](https://github.com/ows0104/Study_EZ_Open/blob/a757ce86c548519b1c1c714298f530f1e9eb86c3/docs/changes/2026-11-05-professor-aware-preview/deployment.md) | ows0104 / Codex 교수별 예습 세션 | [#3](https://github.com/ows0104/Study_EZ_Open/pull/3) |
| 2026-11-05 | master 검사 실패 수정 및 API·웹 배포 완료 (`d5e30590`) — [검사·배포 기록](https://github.com/ows0104/Study_EZ_Open/blob/9f57d3d607335204193441c1358a95fe85b363c7/docs/changes/2026-11-05-ci-regression-fix/deployment.md) | ows0104 / Codex 세션 | [#4](https://github.com/ows0104/Study_EZ_Open/pull/4) |
| 2026-11-05 | 협업 대시보드와 작업 시작 대원칙 도입 | HungryPotato01 / Claude 세션 | [#2](https://github.com/ows0104/Study_EZ_Open/pull/2) |
