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
| P1 | UI/UX 개편 11-07 피드백 운영 반영 | HungryPotato01 / Claude UI 개편 세션 | claude/redesign-1107-feedback | web/src/calendar/(CalendarGrid·CalendarPage·EventChip·ChatSplit·PreviewAction·ReviewAction·ProfessorInfo·kinds), web/src/styles/calendar.css, web/src/notices/GuidePage.tsx, web/tests/(calendar-loading·professor-preview·preview-actions·shared-preview-prompt), docs/changes/2026-11-05-ui-ux-redesign | 2026-11-07 | 시험 칸·빈 막대·N 표시·대화 버튼(C안)·캘린더 머리 단순화·덱 모아받기 보기 제거·스크롤 없앰. 최신 master(#18 포함) 위로 재정렬, tsc·build·캘린더4/4 통과. free-notes의 web/src/styles와는 calendar.css만 겹침(사용자 확인). master 병합=운영 배포라 사용자 승인 대기 |






| P1 | Main-Quiz 문제 퀄리티 — 검사기에 측정 추가(구조 단서-정답 상관·정답 회상 부담·형식 쏠림) | ows0104 / Claude 문제 퀄리티 세션 | claude/bank-quality-checks | studyez_contracts/bank/quality.py, tests/quizbank/test_answer_quality.py(새 파일), docs/changes/2026-11-08-bank-quality-checks | 2026-11-08 | 사용자 2026-11-08 진단 뒤 「검사기에 측정 추가」 선택. 근거: 감염과 면역 261104_02 98문항 중 예/아니오 축 6문항 정답이 전부 부정, basic/list 답 60자 초과 21개, cloze·mcq 0개. 기존 품질 검사는 leaked_units(발문 정답 노출) 하나뿐. errors 아님 — warnings만 추가해 문항을 떨어뜨리지 않고 repair 단계·관리자 issues에 보인다. 선은 운영 Quiz Bank 35편 3,103문항의 p97에서 쟀다. 프롬프트·DB·운영 미변경. 구현·검사 완료 eff75a83 PR #22 https://github.com/ows0104/Study_EZ_Open/pull/22 — 측정 16·contracts·quizbank 720 통과, 전체 pytest 2,098 통과(1 실패는 tests/runner/test_desktop_control.py 바로가기 설치기로 pristine origin/master에서 동일 재현·미수정), 서버 bank 33·경로 171 동일·retention 통과, map_numbers 정상. 실물 대조: 새 Main-Quiz 98문항 errors 0·warnings 36(다섯 측정 모두, Q003·Q080 이름으로), 운영 은행 35편 새 경고 62(편당 중앙 2)·errors 증가 0. master 병합은 사용자 승인 대기 |

| P1 | 감염병리1(261104_02) Map 파이프라인 재구성: 트리형 Map(parent_id)→포인트→개별·구조 문제·검수, 격리 확인 | ows0104 / Claude Main-Quiz 지도 세션(Codex Map 세 작업 승계) | claude/infection-path1-map | content/prompts/learning-links/map-extract*(→/3)·automation/extract-v2.md, studyez_contracts/roots·learning_links 검증, quizbank/connection_generate_v2.py(정규화 부모 보존 검사), tests, docs/changes/2026-11-08-infection-path1-map, runs/_e2e/<새 id> | 2026-11-08 | 사용자 "둘 다 승인"(구현+S1·S2 OpenAI 전송·생성·검수). b4cff4b0 Map /3·부모 보존 검사·실행도구, 계약/파이프라인 검사 285 통과. runs/_e2e/26110801에서 Map·포인트 추출 실행 중. 운영 등록·공개 없음 |

| P1 | Map·독립 출제포인트 추출 프롬프트 정리 | ows0104 / Codex Map 세션 → 2026-11-08 Claude Main-Quiz 지도 세션 승계(사용자 지시: Codex 작업 중단) | codex/map-point-prompts | content/prompts/learning-links/map-extract.md, point-extract.md, *-output.schema.json, *-output.example.json, README.md, docs/changes/2026-11-06-map-point-prompts, .worktrees/map-point-prompts/runs/_map-point-pilot | 2026-11-06 | 사용자 승인 범위의 두 원본 전용 지시문·JSON 스키마·예시·로컬 형식 검증. 현재 사용자 예시 추출 승인: 명시적 OpenAI 전송 승인으로 Map/포인트 각1회 완료, 심내막염·CNS 강의별 JSON4개 보존. 후속 승인된 독립단위 재추출·4지적 보완·별도 재대조 완료: 최종47/60개, ready/ready·잔여issues없음. 원본/중간/실패보존, 필수검사통과, d68b6d57 로컬 검토대기. 운영 요청 재개/문항/게시/배포 없음 |

| P1 | Map 흐름 예시를 반영한 별도 프롬프트 복사본 | ows0104 / Codex Map 참고 세션 → 2026-11-08 Claude Main-Quiz 지도 세션 승계(사용자 지시: Codex 작업 중단) | codex/map-flow-reference | content/prompts/learning-links/map-extract-reference.md, docs/changes/2026-11-06-map-flow-reference, .worktrees/map-flow-reference/runs/_map-flow-experiment | 2026-11-06 | 별도 짧은 지시문 실험 완료: 심내막염20개념/25연결·CNS24개념/31연결, 단일 호출296초. 원본/형식검증·PNG확인. 기존시범/운영미변경. 로컬브랜치 검토대기 |

| P1 | 심내막염·CNS Map→포인트→문제→실제 풀이 E2E 실험 | ows0104 / Codex E2E 세션 → 2026-11-08 Claude Main-Quiz 지도 세션 승계(사용자 지시: Codex 작업 중단) | codex/map-point-e2e | docs/changes/2026-11-06-map-point-e2e, runs/_e2e/26110507 (실험 전용 저장소·격리 DB·로컬 앱), 기존 추출 결과 읽기 전용 | 2026-11-06 | CNS49문항 중40과제 실제UI·응답/진도 새로고침 복원·별도 기술계정 사건 저장 확인. 사람기록0 유지해 풀이 링크/JSON 제공. 심내막염47문항 최종 source-2/medical-2 완료했으나 서로 다른 C001/C012 중복으로 BANK등록 실패·3회상한 도달 보류(40ok/6doubt/1wrong). 양강의 완료 아님. 원본740파일·실패/소비보존, 운영548/DB/은행/학습/배포변경없음. 로컬 검토대기 |









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
| 2026-11-08 | 미리보기 원본 해시 검사 간헐 실패 수정: _digest 캐시 키(경로·크기·mtime_ns)에 같은 29바이트 다시 쓰기가 같은 mtime을 받으면 옛 해시. 검사만 고쳐 mtime을 1초 앞당김(같은 mtime 강제로 재현, 30회 연속·파일 18개 통과). 런타임 코드·DB 미변경. PR CI 통과, 병합 8d583535, master 실행 42399468633 검사·API 배포 성공 | ows0104 / Claude CI 실패 점검 세션 | [#27](https://github.com/ows0104/Study_EZ_Open/pull/27) |
| 2026-11-08 | 사람 승인을 되돌릴 수 없는 작업으로 좁힘: 구현 계획·되돌릴 수 있는 코드 배포(master 병합 포함)는 작업 요청을 근거로 진행, 따로 묻는 것은 docs/development/README.md 「사람에게 묻는 것」 목록뿐(운영 DB 쓰기·학습 기록·권한·복구 불가 삭제·외부 전송). 문서만, 도구 미변경. PR CI Tests and build 통과, 병합 c8133cec | ows0104 / Claude 승인 범위 세션 | [#26](https://github.com/ows0104/Study_EZ_Open/pull/26) |
| 2026-11-08 | 뿌리 학습(Main-Quiz) 읽기 경로 지연: 개인 수정 N+1(98과제=98질의)→1질의, 은행 지문 캐시, 판 목록·참고 PDF 큰 JSON 지연 로딩, PDF.js 범위 읽기(15.9MB 한 쪽 16.5→1.9MB). 새 검사(수정 전 실패 확인)·서버 122·웹 빌드·PR CI 통과. 병합13956805, 배포는 #25·#26과 함께 c8133cec(API health SHA·트래픽 100%·Pages 번들 옵션 확인). 수정 뒤 운영 지연은 실사용 뒤 측정 예정 — [배포 기록](https://github.com/ows0104/Study_EZ_Open/blob/claude/root-learning-load/docs/changes/2026-11-08-root-learning-load/deployment.md) | ows0104 / Claude 사이트 로딩 진단 세션 | [#24](https://github.com/ows0104/Study_EZ_Open/pull/24) |
| 2026-11-08 | 관리자 generation GET이 result·web_dispatch·web_response를 defer, dispatched·awaitingWeb 참/거짓은 같은 SELECT에서 SQL로, report는 (판 id, result_digest)당 한 번 캐시. 응답·DB 스키마·웹 미변경. 새 검사(수정 전 실패·응답 동일성 9상황)·서버 122/122·PR CI 통과. PR25 병합 06a01211(사용자 계정) — 그 SHA 배포는 master 전진으로 assert_head 거부, c8133cec(PR26) 실행으로 반영. health SHA·401 확인. **운영 지연 미확인** — 배포 뒤 로그인 관리자 요청 0건(수정 전 3–15s, #21 뒤 2.3s 표본1). 관리자 화면 첫 요청은 result 한 번 읽음, 둘째부터 비교 — [배포·측정 기록](https://github.com/ows0104/Study_EZ_Open/blob/claude/root-generation-columns/docs/changes/2026-11-08-root-generation-columns/deployment.md) | ows0104 / Claude generation 칼럼 세션 | [#25](https://github.com/ows0104/Study_EZ_Open/pull/25) |
| 2026-11-08 | Main-Quiz 로딩 지연 재발 1차: 관리자 generation 질의에 LIMIT 1, 폴링을 앞 응답 뒤로, Cloud Run concurrency 80→8. PR21 병합 4f48b2a5 — 그 SHA 배포는 검사 중 master 전진으로 assert_head가 거부, cc67288b(PR22) 실행으로 반영. health SHA·401·트래픽 revision concurrency 8·배포된 웹 청크 setInterval 0회 확인. 서버121·root20·저장소회귀2068·웹빌드·웹단위7·실제 Chrome 5 PASS. **증상 잔존** — 새 revision의 유일한 실제 구간에서 261104_02 generation GET 2.323s(수정 전 median 2.736s). 같은 구간 /api/me 0.961s(따뜻할 때 0.033s)라 한 표본으로 몫을 가를 수 없다. 격리 SQLite는 2.5MB result에서도 0.045s이므로 남은 설명은 Supabase 전송. 다음 수(폴링 경로에서 result 미적재)는 claude/root-learning-load가 claim한 「큰 JSON 칼럼 지연 로딩」과 겹쳐 손대지 않았다. 출제·은행·학습 기록·DB 미변경 — [배포·측정 기록](https://github.com/ows0104/Study_EZ_Open/blob/claude/main-quiz-load-contention/docs/changes/2026-11-08-main-quiz-load-contention/deployment.md) | ows0104 / Claude 로딩 지연 세션 | [#21](https://github.com/ows0104/Study_EZ_Open/pull/21) |
| 2026-11-08 | master 직접 push 차단 로컬 pre-push 훅(.githooks/pre-push·install.sh, .git/hooks 복사 설치). GitHub 비공개+무료 플랜이라 서버측 보호·ruleset 403 → 로컬 훅. master push·삭제와 DASHBOARD.md 담은 브랜치 거부, 실제 push 7경우·worktree 3곳 확인. core.hooksPath 방식은 옛 커밋 worktree에서 보호가 빠져 미채택. --no-verify·미설치 클론·웹 병합은 못 막음. 상대방 클론은 `sh .githooks/install.sh` 1회 필요. 같은 세션에서 병합 끝난 로컬 브랜치 108개·원격 5개 정리, 배포 기록 담은 브랜치 13개는 보존 | ows0104 / Claude 브랜치 정리 세션 | [#23](https://github.com/ows0104/Study_EZ_Open/pull/23) |
| 2026-11-07 | Main-Quiz 참고슬라이드 API 경유(R2 CORS 없음 우회, Range)·개념지도 트리형. PR19 병합ef40ddfe(자체 배포는 PR18 병합으로 대체되어 거부), master e73ccf0a 전체CI·API 배포 성공. 운영 health SHA·새 경로 401·Range preflight 허용·expose 헤더·openapi 경로·Pages 새 트리/proxyPath 청크 확인. 로그인 화면 슬라이드 렌더링은 학습 기록(답 열람) 쓰기 필요로 미확인. 학생 공개 미변경 | ows0104 / Claude Main-Quiz 지도 세션 | [#19](https://github.com/ows0104/Study_EZ_Open/pull/19) |
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



