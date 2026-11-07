# 작업 지도

고칠 기능을 찾고 해당 행의 파일부터 읽는다. 폴더별 `CLAUDE.md`에는 계약과 검사만 있다.

## 작업 범위부터 선택

| 영역 | 먼저 읽을 곳 | 연결된 검사 |
|---|---|---|
| 사이트 | web/CLAUDE.md, server/CLAUDE.md, 해당 화면/API | 웹 typecheck/build, 해당 서버 테스트 |
| 출제 | quizbank/CLAUDE.md, content/prompts/CLAUDE.md | tests/quizbank |
| 연결부 | runner/CLAUDE.md, bridge/CLAUDE.md | tests/runner, tests/bridge |
| 공용 계약 | studyez_contracts/CLAUDE.md, artifact-contract.md | tests/contracts + 생산자/소비자 |
| 독립 앱 | spotter/CLAUDE.md | tests/spotter + 공유 인증 |
| 개발·운영 루프 | [개발 절차](development/README.md), scripts/development.py, scripts/maintenance.py | tests/development |

독립 영역과 실제 보관 위치는 [제품 경계와 보관](components-and-archives.md)을 본다.
Spotter 검색은 `rg --no-ignore <검색어> spotter/scripts spotter/web`로 범위를 지정한다.

새 작업 기록은 `docs/changes/<id>/`에 만든다. work/tmp/runs는 필요한 경로를 지정한 경우만 읽는다.

## Study_EZ

| 할 일 | 시작할 파일 |
|---|---|
| 캘린더·강의 패널 | [web/src/calendar](../web/src/calendar), [web/src/types/lectures.ts](../web/src/types/lectures.ts) |
| 덱 생성 진행 표시 | [DeckSlot.tsx](../web/src/calendar/DeckSlot.tsx), [jobProgress.ts](../web/src/jobProgress.ts) |
| 기존 예습·복습 풀이 | [web/src/lecture](../web/src/lecture), [server/app/srs.py](../server/app/srs.py) |
| Quiz Bank 시작·개념 지도 | [BankStart.tsx](../web/src/bank/BankStart.tsx), [ConceptMap.tsx](../web/src/bank/ConceptMap.tsx) |
| 뿌리 학습·목표 집계·오늘 추천 | [RootLearning.tsx](../web/src/bank/RootLearning.tsx), [전용 API](../server/app/routes/root_learning.py), [구현 기록](changes/2026-11-02-root-learning-product/implementation.md) |
| 강의별 연결 학습·근거·자료 등록 | [ConnectionLearning.tsx](../web/src/bank/ConnectionLearning.tsx), [서버 API](../server/app/routes/connections.py), [제품 구현 기록](changes/2026-11-03-connection-learning-product/implementation.md) |
| Quiz Bank 풀이·문항 표시 | [BankSolve.tsx](../web/src/bank/BankSolve.tsx), [BankQuestion.tsx](../web/src/bank/BankQuestion.tsx) |
| Quiz Bank 생성·공개 | [BankPanel.tsx](../web/src/bank/BankPanel.tsx), [publication.py](../server/app/routes/bank_api/publication.py) |
| Main Quiz CLI 병렬 출제·개념도·포인트·그림 | [병렬 생성기](../quizbank/connection_parallel.py), [원본 그림 목록](../quizbank/connection_figures.py), [러너 개별 진행](../runner/parallel_status.py), [실행·검증 기록](changes/2026-11-06-cli-parallel-main-quiz/intent.md) |
| Concept map·포인트 자동출제·게시 | [요청 화면](../web/src/bank/RootGenerationPanel.tsx), [전용 API](../server/app/routes/root_generation.py), [생성기](../quizbank/connection_generate.py), [구현·운영 조건](changes/2026-11-03-connection-generation-pipeline/implementation.md) |
| 뿌리 생성의 큰 JSON·시간 초과·모델 제한 | [공통 파일 실행·실패 구분](../runner/root_native_json.py), [기존 실패의 명시적 재사용](../runner/root_transport_recovery.py), [실행·검증 기록](changes/2026-11-05-root-timeout-fix/live.md). 원래 수용·독립 검수·상한을 유지하며 공급자 콘텐츠 거절은 재호출·게시 보류 |
| Quiz Bank API 책임·검사 지도 | [bank_api/CLAUDE.md](../server/app/routes/bank_api/CLAUDE.md) |
| Quiz Bank 생성 프롬프트 | [bankPrompt.md](../content/prompts/bank/bankPrompt.md) |
| Quiz Bank 정리·검증 | [quizbank/CLAUDE.md](../quizbank/CLAUDE.md) |
| 연결·문항·중요성 근거 로컬 검토 묶음 | [입력 안내](../content/prompts/learning-links/README.md), [connection_plan.py](../quizbank/connection_plan.py), [공용 계약](../studyez_contracts/learning_links/validate.py) |
| 다음 문항·숙련도 | [server/app/study_engine](../server/app/study_engine) |
| 관리 화면·사용 현황 | [web/src/admin](../web/src/admin), [usage.py](../server/app/routes/usage.py) |
| 오류 제보·사이트 개선 루프 | [운영 안내](feedback-loop.md), [runner/feedback.py](../runner/feedback.py) |
| 공지·이용방법 | [web/src/notices](../web/src/notices), [notices.py](../server/app/routes/notices.py) |
| 자유 노트(블록 편집기·태그) | [web/src/notes](../web/src/notes), [notes.py](../server/app/routes/notes.py), [구현 기록](changes/2026-11-07-free-notes/spec.md) |
| 카드 수정과 덱 반영 | [cards.py](../server/app/routes/cards.py), [runner/site_edits.py](../runner/site_edits.py), [quizgen/site_edits.py](../quizgen/site_edits.py) |
| 로그인·API 요청 | [web/src/auth.tsx](../web/src/auth.tsx), [web/src/api.ts](../web/src/api.ts), [server/app/auth.py](../server/app/auth.py) |
| 화면 색·여백 | [web/src/styles](../web/src/styles) |
| 덱 모아받기 | [web/src/bundle](../web/src/bundle), [bundles.py](../server/app/routes/bundles.py) |

## 생성·러너·서버

| 할 일 | 시작할 파일 |
|---|---|
| 러너 명령 옵션·분기 | [runner/cli](../runner/cli) |
| 자료 탐색·연도 매칭 | [runner/watch.py](../runner/watch.py), [runner/filenames.py](../runner/filenames.py), [runner/matching.py](../runner/matching.py) |
| 족보 정리·PDF 첨부 | [공통 형식 정책](policies/jokbo-attachments.md), [runner 안내](../runner/CLAUDE.md#족보) |
| 자동 작업 실행·대기 | [runner/agent.py](../runner/agent.py), [runner/cycle.py](../runner/cycle.py) |
| 상태 판정·재시도 기록 | [runner/agent_state.py](../runner/agent_state.py) |
| 생성기 실행·계약 변환 | [runner/deck.py](../runner/deck.py), [은행 러너 지도](../runner/bank_flow/CLAUDE.md) |
| 업로드·보류 판정 | [runner/publish.py](../runner/publish.py), [runner/gate.py](../runner/gate.py) |
| HTTP·파일 전송 | [runner/transport.py](../runner/transport.py), [은행 업로드](../runner/bank_flow/upload.py) |
| 시도 선택·폴더 위치 | [runner/runlayout.py](../runner/runlayout.py), [runner/chosen.py](../runner/chosen.py) |
| 덱 생성 단계·재시도 | [quizgen/run.py](../quizgen/run.py), [quizgen/prequiz/run.py](../quizgen/prequiz/run.py) |
| 카드 작성 지침 | [프롬프트 조립 안내](prompt-architecture.md), [quizgen/prompts](../quizgen/prompts) |
| 카드 검증·재현 검사 | [quizgen/validate.py](../quizgen/validate.py), [quizgen/reproduce.py](../quizgen/reproduce.py) |
| Anki 덱 생성·카드 디자인 | [quizgen/build.py](../quizgen/build.py), [quizgen/anki_models.py](../quizgen/anki_models.py) |
| API 경로 | [server/app/routes](../server/app/routes) |
| DB 모델 | [server/app/models](../server/app/models) |
| 서버 작업 정책 | [server/app/jobs](../server/app/jobs), [prequiz_jobs.py](../server/app/routes/prequiz_jobs.py) |

## 땡시·확장

| 할 일 | 시작할 파일 |
|---|---|
| 땡시 데이터·화면 | [spotter/CLAUDE.md](../spotter/CLAUDE.md) |
| 예습 링크·Quiz Bank 답 회수 | [bridge/CLAUDE.md](../bridge/CLAUDE.md), [web/src/bridge](../web/src/bridge) |
| 예습 URL 검증 | [server/app/preview_links.py](../server/app/preview_links.py) |
| 공용 로그인 세션 | [platform/session/session.js](../platform/session/session.js) |

검사는 [명령 안내](commands.md#검사), 전체 흐름은 [현재 구조](architecture.md)를 본다.
이 지도에는 코드 줄 수·검사 수를 복제하지 않는다. 구조 점검은
`python scripts/map_numbers.py --check`로 실행한다.
