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
| P2 | 자유 노트(Notion식 편집기·태그) 서버 저장 | HungryPotato01 / Claude 자유 노트 세션 | claude/free-notes | server/app/models/notes.py·routes/notes.py(새 표 user_note+RLS), server/app/main.py·models/__init__.py, server/tests/test_notes.py·test_route_contract.py, web/src/notes/*, web/src/App.tsx, web/src/shell/Sidebar.tsx·icons.tsx, web/src/styles, docs/changes/2026-11-07-free-notes | 2026-11-07 | 2단계 중 자유 노트만(회독 기록은 2번에 남김). 프로토타입 형태, "강의"→자유 태그. 2026-11-07 구현 승인 → 8ba063d PR #18 https://github.com/ows0104/Study_EZ_Open/pull/18 , 서버 전체119·notes·경로170·웹 build 통과, 격리 로컬DB 브라우저 확인. 운영 DB user_note 생성·master 병합은 별도 승인 대기 |


| P1 | Map·독립 출제포인트 추출 프롬프트 정리 | ows0104 / Codex Map 세션 | codex/map-point-prompts | content/prompts/learning-links/map-extract.md, point-extract.md, *-output.schema.json, *-output.example.json, README.md, docs/changes/2026-11-06-map-point-prompts, .worktrees/map-point-prompts/runs/_map-point-pilot | 2026-11-06 | 사용자 승인 범위의 두 원본 전용 지시문·JSON 스키마·예시·로컬 형식 검증. 현재 사용자 예시 추출 승인: 명시적 OpenAI 전송 승인으로 Map/포인트 각1회 완료, 심내막염·CNS 강의별 JSON4개 보존. 후속 승인된 독립단위 재추출·4지적 보완·별도 재대조 완료: 최종47/60개, ready/ready·잔여issues없음. 원본/중간/실패보존, 필수검사통과, d68b6d57 로컬 검토대기. 운영 요청 재개/문항/게시/배포 없음 |

| P1 | Map 흐름 예시를 반영한 별도 프롬프트 복사본 | ows0104 / Codex Map 참고 세션 | codex/map-flow-reference | content/prompts/learning-links/map-extract-reference.md, docs/changes/2026-11-06-map-flow-reference, .worktrees/map-flow-reference/runs/_map-flow-experiment | 2026-11-06 | 별도 짧은 지시문 실험 완료: 심내막염20개념/25연결·CNS24개념/31연결, 단일 호출296초. 원본/형식검증·PNG확인. 기존시범/운영미변경. 로컬브랜치 검토대기 |

| P1 | 심내막염·CNS Map→포인트→문제→실제 풀이 E2E 실험 | ows0104 / Codex E2E 세션 | codex/map-point-e2e | docs/changes/2026-11-06-map-point-e2e, runs/_e2e/26110507 (실험 전용 저장소·격리 DB·로컬 앱), 기존 추출 결과 읽기 전용 | 2026-11-06 | CNS49문항 중40과제 실제UI·응답/진도 새로고침 복원·별도 기술계정 사건 저장 확인. 사람기록0 유지해 풀이 링크/JSON 제공. 심내막염47문항 최종 source-2/medical-2 완료했으나 서로 다른 C001/C012 중복으로 BANK등록 실패·3회상한 도달 보류(40ok/6doubt/1wrong). 양강의 완료 아님. 원본740파일·실패/소비보존, 운영548/DB/은행/학습/배포변경없음. 로컬 검토대기 |









## 2. 앞으로 하기로 약속된 일


| 우선순위 | 작업 | 예정 작업자 | 예상 영역·파일 | 선행 조건·메모 |
|---|---|---|---|---|
| P2 | UI/UX 개편 2단계: 강의록 회독 기록(+/삭제/되돌리기) 서버 저장 (자유 노트는 1번 claude/free-notes로 분리 시작) | HungryPotato01 / Claude | server/app/models·routes(새 표 2개+RLS), server/app/cli.py, web/src/notes/*, web/src/calendar/EventPanel.tsx | 2026-11-06 사용자 결정으로 1단계와 분리. 새 표·API라 운영 DB 준비·중요 운영 승인 필요. 1단계 PR #9 병합 후 시작. 사용자 2026-11-07 조정 승인: codex/review-quiz-entry가 EventPanel의 복습퀴즈 활성화 조건만 먼저 수정 |
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
| 2026-11-07 | 복습퀴즈 버튼 활성화 조건만 수정. 새 자료/기존 은행/없음 3상태 브라우저 및 웹·PR전체CI 통과. PR17 병합75ada218·사용자 배포 승인. master CI/API42371918796·Pages82ad1c19 동일SHA 반영 성공. 실제 EventPanel 새조건 확인·운영 학습쓰기0 | ows0104 / Codex 버튼 수정 | [#17](https://github.com/ows0104/Study_EZ_Open/pull/17) |
| 2026-11-07 | Main-Quiz 약리 UI 복원 PR16 병합 b8a9540a. 사용자 병합/사이트 반영 승인. 네 평가 자유선택·답 입력 제거·참고 PDF·개념지도. 로컬 웹/서버14/브라우저3 및 PR 전체CI 통과. master 전체CI/API 배포42369151301·Pages219bb8bf 같은SHA 반영 성공. 실제 health/웹 네 평가·PDF worker/CMap·401 확인, 운영 학습쓰기0 | ows0104 / Codex UI 복원 | [#16](https://github.com/ows0104/Study_EZ_Open/pull/16) |
| 2026-11-07 | Main Quiz 새판 PR14 병합a4625641. 실제CLI104전체안held·수정3/3 보관, 별도범위검수 승인98문항98과제·이미지12문항14장, 의학/그림보류6·중요도미확정6중립화. 239계약/러너·서버6·실제격리UI·PR전체CI 통과. master 전체CI(기존mtime 간헐실패1회 동일SHA 재검사통과)·API/Pages a4625641 배포 성공. 실제261104_02 새98문항98과제·이미지12문항14장 반입/별도프로세스 readback·원본PDF실제다운로드·전체PNG SHA 확인. 사람기록0·학습쓰기0·UI동일·관리자시범범위유지·과거판보관·다른강의미실행. [실제배포기록](https://github.com/ows0104/Study_EZ_Open/blob/codex/main-quiz-task-relink/docs/changes/2026-11-07-main-quiz-task-relink/deployment.md) | ows0104 / Codex Main Quiz 후속 | [#14](https://github.com/ows0104/Study_EZ_Open/pull/14) |
| 2026-11-07 | 복습 개인링크 기본 문구를 올해 필기·족보 기반 큰 흐름 요청으로 교체하고 올해 교수 한 줄 표시. 관련 검사5개·웹 타입/빌드·PR/master 전체 CI 통과, 2d85e793 API/Pages 배포 성공. 실제 공개 복습 자산의 새 문구/긴 안내 제거·동일API SHA·401 확인. 기존 개인 문구·예습·자료·학습 기록 보존 — [배포 근거](https://github.com/ows0104/Study_EZ_Open/blob/codex/review-prompt-simple/docs/changes/2026-11-07-review-prompt-simple/deployment.md) | ows0104 / Codex 복습 문구 세션 | [#15](https://github.com/ows0104/Study_EZ_Open/pull/15) |
| 2026-11-07 | Main Quiz 원클릭·CLI3작업 병렬/개별진행·분할검수/기존복구 통합 PR13 병합2489e52e. 전체CI 통과. 실제261104_02 최종91문항·그림15문항19장·49과제, C005한행CLI/새전체대조 완료 수정3/3; 기존문항/판정/22검수/실패보존, 격리UI/원본PDF링크 통과. API/Pages2489e52e 동일SHA 배포성공·관리자시범 실제반입/원본PDF서명링크실제다운로드/19PNG해시 확인. 기존은행/사람학습기록불변·학습사건쓰기0. 러너바로가기 고정코드로 갱신(작업시작0), 격리서버종료·기록보존. 사슬알균미실행 | ows0104 / Codex Main Quiz 후속 | [#13](https://github.com/ows0104/Study_EZ_Open/pull/13) (PR10/11/12와 인계복구 포함) |
| 2026-11-06 | UI/UX 개편 1단계(웹만) 구현·검사 완료: 좌측 메뉴·흰 바탕·색 5조합·캘린더(D-day·회독·학습률)·강의 패널·강의 목록·감염과 면역 1차/2차 블럭·강의 번호. 서버·DB·출제 미변경. 병합(=운영 배포)은 사용자 확인 후 | HungryPotato01 / Claude UI 개편 세션 | [#9](https://github.com/ows0104/Study_EZ_Open/pull/9) (병합 전) |
| 2026-11-06 | 새 파이프라인의 Main Quiz 통합(회상 단위 PR7 포함) 7b96003f master 반영. 필수 계약644·서버52·웹27·CUA15 통과. API·Pages7b96003f 같은SHA 배포 및 실제 Main Quiz assets 대조 완료(한국15:16:51 게시). [배포 기록](https://github.com/ows0104/Study_EZ_Open/blob/codex/main-quiz-unified/docs/changes/2026-11-06-main-quiz-unified/deployment.md). 직접 게시 준비는 자동복구로 종료·수동 업로드0. GuidePage 인계: 새 화면 Space/Enter 답 확인·1/2/3 회상평가·Z 취소, 기존 은행4등급/기록 유지 | ows0104 / Codex Main Quiz 세션 | [#8](https://github.com/ows0104/Study_EZ_Open/pull/8) |
| 2026-11-05 | 순수 JSON 수신·검증·결정적 변환과 프롬프트 1.82 API·웹 a3f67d13 배포 완료. 전체 검사/health SHA/401/운영 프롬프트 확인. 로컬 러너 코드 갱신·기존 매칭 보존. 브리지 1.3.23 사용자 업데이트 필요 — [배포 기록](https://github.com/ows0104/Study_EZ_Open/blob/codex/bank-json-delivery/docs/changes/2026-11-05-bank-json-delivery/deployment.md) | ows0104 / Codex JSON 전환 세션 | [#6](https://github.com/ows0104/Study_EZ_Open/pull/6) |
| 2026-11-05 | 교수별 예습·CBL 매핑과 적용 기록 master 반영 및 API·웹 `5c56d462` 배포 완료. 양쪽 전체 검사/health/401/Pages success/CBL 세 첨부 유지 확인 — [배포 기록](https://github.com/ows0104/Study_EZ_Open/blob/04e60a2df003dcb7688e3678457754a13d506577/docs/changes/2026-11-05-cbl-prev-notes/repository-deployment.md) | ows0104 / Codex 교수별 예습 세션 | [#5](https://github.com/ows0104/Study_EZ_Open/pull/5) |
| 2026-11-05 | 미정 CBL 3개에 주제와 관련 CBL 기출을 확인한 2025년 필기 연결 완료. 세 PDF 실제 해시/학습 기록 보존/운영 화면 확인 및 러너 복원. 코드 재배포 없음 — [운영 기록](https://github.com/ows0104/Study_EZ_Open/blob/2d420b1f78f670f0dfa205bd0b86917bc7b0f675/docs/changes/2026-11-05-cbl-prev-notes/deployment.md) | ows0104 / Codex 교수별 예습 세션 | 승인된 자료 연결, 기록 codex/cbl-prev-notes |
| 2026-11-05 | 교수 변경·신규 교수 표시 및 최근 5년 동일 교수 최신 필기 우선, 없으면 작년 대체 운영 반영 (`c86e15fb`). 84개 강의·기록 보존, PDF 72개 실제 검증, 러너 복원 완료 — [배포 기록](https://github.com/ows0104/Study_EZ_Open/blob/a757ce86c548519b1c1c714298f530f1e9eb86c3/docs/changes/2026-11-05-professor-aware-preview/deployment.md) | ows0104 / Codex 교수별 예습 세션 | [#3](https://github.com/ows0104/Study_EZ_Open/pull/3) |
| 2026-11-05 | master 검사 실패 수정 및 API·웹 배포 완료 (`d5e30590`) — [검사·배포 기록](https://github.com/ows0104/Study_EZ_Open/blob/9f57d3d607335204193441c1358a95fe85b363c7/docs/changes/2026-11-05-ci-regression-fix/deployment.md) | ows0104 / Codex 세션 | [#4](https://github.com/ows0104/Study_EZ_Open/pull/4) |
| 2026-11-05 | 협업 대시보드와 작업 시작 대원칙 도입 | HungryPotato01 / Claude 세션 | [#2](https://github.com/ows0104/Study_EZ_Open/pull/2) |



