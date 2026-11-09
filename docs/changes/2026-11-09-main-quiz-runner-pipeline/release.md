# Main-Quiz 생성 러너 일반화 — 배포 준비

## PR A — 계약·엔진 (R4 보완 예산, R5 검토 포기)

사용자 2026-11-09 「PR A 시작」.

### 바뀐 것
- **새 실행 정책**: 생성기가 새 ledger를 만들 때 `runPolicies: ['initial-correction-separate/1', 'review-retry/1']`을 적고, manifest에도 싣는다.
  - 대상: `quizbank/connection_generate_v2.py`, `studyez_contracts/roots/generation_v2.py`
- **보완 예산(R4)**
  - 초기 지도 오류는 지금처럼 첫 출제에 전달한다. 다만 보완 회차로 세지 않는다(`initialMapCorrection.consumedRounds: 0`).
  - 보완은 언제나 최대 `repair-1..3`이다.
  - 계약은 정책과 `consumedRounds`가 맞는지 검사한다(`charged_initial_rounds`).
- **검토 포기(R5)**: 원본 대조 단계만 새 세션으로 한 번 다시 돈다. 대상은 두 경우다.
  - `UNPERFORMED_REVIEW`: 같은 세션 되돌려주기 뒤에도 아무것도 판정하지 않음
  - 맥락 검사 경로에서 마지막 회차 원본 대조의 `clinical_context_status == 'unknown'`

  처리 방식은 다음과 같다.
  - 버린 단계와 `.native/<단계>`는 `.retry-<단계>/`로 옮긴다. 지우지 않는다.
  - ledger·manifest의 `reviewRetries`에 남는 것: 단계, 종류, 재개 뒤 몇 번째 실행인지(`afterResumes`), 버린 단계 기록, 옮긴 파일
  - 두 번째 포기는 멈춘다. 빈 판정은 원래 오류로 멈춘다. 마지막 unknown은 「두 번 unknown」 메시지로 멈춘다.
- **계약 검사**
  - `validate_review_retries`가 검사하는 것: 단계당 1회, 정책 필요, 같은 입력, 다른 raw. 뒤에 사람이 이어 하기로 바꾼 단계는 예외다.
  - `validate_stage_resumes`는 재개 뒤 재실행으로 바뀐 단계를 허용한다.
  - 정책이 있는 실행은 수동 복구 이력을 받지 않는다(`run_policies`). 대상: `RECOVERY_HISTORY`, `runtimeRevalidations`, `normalizationRecoveries`, `parallelSchemaRecovery`, `chunkedReview`, `planRepair`
- **러너**: `runner/root_native_json.validate_all`이 `.retry-<단계>/`의 보관 파일이 있는지 확인한다.
- **수동 복구 도구 13개**: ledger를 읽자마자 `require_legacy_ledger`로 새 정책 ledger를 거절한다.
  - 이전에는 「Changed correction allowance」 같은 문구로 뒤늦게 실패했다.
  - `root_plan_repair`·`root_task_supplement`·`root_quiz_curation`은 자기 고정 조건과 계약에서 막힌다.
- **문서**: `quizbank/CLAUDE.md`의 「총3회 중1회를 먼저 소비」를 새 정책과 옛 기록 규칙으로 고쳤다. `spec.md`의 필드 이름을 실제(`runPolicies`)에 맞췄다.

### 옛 기록의 호환
- 정책이 없는 ledger는 옛 규칙으로 돈다. 이어 하기(`--resume`)로도 정책이 바뀌지 않는다(검사 `test_recorded_legacy_ledger_keeps_the_shared_budget_when_resumed`).
- 공개된 두 강의 결과(읽기만):

  | 결과 | 과제 | 재검증 |
  |---|---|---|
  | `26110803/generation-3` | 57 | `validate_result`·`validate_all` 통과 |
  | `26110901/generation-4` | 96 | `validate_result`·`validate_all` 통과 |

  두 결과 모두 결과 파일 sha는 그대로다.
- 옛 복구 도구 검사 5개 파일은 `legacy_ledgers` fixture로 옛 기록을 만들어 그대로 돈다. 도구의 동작은 바뀌지 않았다.

### 검사
- 새 검사: `tests/quizbank/test_run_policies.py` 16개, `tests/runner/test_root_native_json.py` 1개 추가·1개 갱신
  - 구현 전에는 16개 중 15개가 실패했다. 통과한 1개는 수동 이력 거절 검사였다. 그때는 옛 계약이 다른 이유로 거절했다.
- `tests/contracts`·`tests/quizbank`·`tests/runner` 전체: 1,578 통과, 실패 2개
  - `test_desktop_control::test_shortcut_installer_supports_korean_filename_in_windows_powershell`: master에서도 실패하는 기존 결함
  - `test_root_native_json::test_review_stages_get_every_page_and_stimulus_image_in_their_first_message`: 간헐 실패. 아래에 따로 적는다.
- 서버 `-m tests root`(worktree 계약, 격리 sqlite): 27개 전부 통과
- 모델 호출·운영 DB 쓰기: 없음

### 간헐 실패 — master에도 있던 ledger 읽기 경합 (같이 고침)
- **증상**: `test_root_native_json`의 speed 경로 검사가 가끔 `PermissionError: ... ledger.json`으로 실패한다.
  - 이 브랜치에서 약 20회 중 2회 실패했다.
  - master 95482162에서도 8번째 반복에서 `test_speed_path_context_stage_runs_through_native_files_and_stays_verifiable`가 같은 오류로 실패했다.
- **원인**: 맥락 검사 경로에서는 원본 대조와 정답 검수가 스레드 둘로 동시에 돈다.
  - 원본 대조 쪽 `NativeJson.require_unblocked`는 ledger.json을 잠금 없이 읽는다.
  - 같은 순간 정답 검수 쪽이 ledger를 원자적으로 교체하면, Windows가 읽기를 잠깐 거절한다.
  - 운영 실행에서도 같은 경로로 단계가 실패할 수 있다.
- **수정**: `runner/root_native_json.read_shared`가 PermissionError일 때 짧게 다시 읽는다(5회). 쓰는 쪽(`connection_generate.write`)이 이미 같은 방식으로 재시도한다.
  - 검사 1개 추가: 두 번 거절 뒤 읽으면 통과하고, 계속 거절이면 그대로 실패하는지 본다. 수정 전 코드는 첫 거절에서 실패한다.
- **수정 뒤 반복 결과**: 모듈 10회 반복 모두 39개 통과, 실패 0.

### 배포 (PR A)
- 병합: 2026-11-09 #60 → master 70f1fad5. 사용자 「병합하고 PR B」.
- 「Test and deploy」 워크플로가 성공했다.
- 운영 API `/api/health`: `{"environment":"production","revision":"70f1fad5…"}`. 병합 SHA와 같다.
- DB 스키마 변경과 데이터 변경은 없다.
- 러너 배포 사본은 아직 옛 코드다. 새 정책은 러너를 다시 띄운 뒤 시작하는 생성부터 적용된다.

## PR B — 앞 단계·파생 packet·러너 분기 (R2, R3, R6 러너 쪽)

사용자 2026-11-09 「병합하고 PR B」. 브랜치 `claude/main-quiz-runner-front`.

### 바뀐 것
- **지시문**: 시범 `run.py`에 직접 짜여 있던 대조·보완 지시문과 대조 스키마를 옮겼다. 추출 뒤에 붙이던 문구도 함께 옮겼다.
  - 위치: `content/prompts/learning-links/map-tree/`(파일 4개 + README)
  - 강의 제목·쪽 범위 자리만 `$` 변수로 바꿨다.
  - 사슬알균 값으로 채우면 시범이 실제로 보낸 task.md 다섯 개와 글자 하나까지 같다. 이것을 `tests/fixtures/map_tree_26110901/`에 기준으로 두고 검사한다.
- **`studyez_contracts/roots/map_tree.py`(새 파일)**
  - `lecture_scope`: 제목과 쪽 수만으로 범위 문장을 만든다. 시범 SCOPE의 강의 고유 사실(기출 연도·교수)은 만들어 넣지 않는다. 족보 PDF 머리 표시를 따르게 한다.
  - `derive_packet`: 서버 요청에서 시범 packet과 같은 형태의 생성 packet을 결정적으로 만든다. 형태는 `provided`, `source-assessment/2`, `speedStages`, 시범 범위 덧붙임 문구다.
  - `resolve`: 결과의 `manifest.derivedPacket`을 요청에서 다시 만들어 맞는지 본다.
  - 앞 단계 증거(`frontStages`)를 검사한다: 단계 순서, 출력 해시, 대조 판정, 「지적이 있을 때만 보완 1회」, 재개 이력, Map 트리, 포인트 중요도 계산 가능, 쪽 범위.
- **`automation.validate_result`**: `pipeline`이 있는 요청은 `resolve` 뒤 기존 검증을 한다. 서버 `put_result`와 러너가 이 경로를 쓴다.
  - `generation_v2.validate_result`는 파생 packet으로 돈 결과가 그 packet을 manifest에 싣고 있는지 확인한다.
- **`runner/root_front.py`(새 파일)**: 시범 `run.py`의 prepare~packet 단계를 요청 packet 입력으로 옮겼다.
  - 상수와 경로를 없앴다.
  - 단계마다 Codex 호출 1회, 입력 고정, 영수증 확인, 실패 보관, 자동 재실행 없음은 시범과 같다.
  - `--resume <이유>`가 있으면 실패 단계와 그 뒤 단계를 `.resume-<k>/`로 옮기고 다시 돈다.
  - 쪽 이미지는 PyMuPDF 100 dpi로 만든다(시범은 pdftoppm -r 100).
- **`runner/connection_generation.run_generation`**
  - map-tree 요청이면 다음 순서로 돈다: `root_front` → 파생 packet 재검증 → `<gid>/generation/`에서 `root_native_json` → `validate_result(결과, 요청)` → 게시.
  - `resume` 인자와 러너 CLI `--generation-resume`을 더했다. 이 값이 앞 단계와 생성 단계에 `--resume`으로 간다. 서버가 이 값을 보내는 일은 PR C다.
- **문서**: `runner/CLAUDE.md`, `map-tree/README.md`, spec의 출력 폴더와 쪽 이미지 줄.

### 검사
- `tests/contracts/test_map_tree.py` 22개: 범위 문장, 요청 조건, 앞 단계 증거 위변조, 출력 검사, `resolve`, 모르는 pipeline 거절
- `tests/runner/test_root_front.py` 12개
  - 지시문이 시범과 같은지(바이트 단위)
  - 대조 통과·지적·족보 없는 요청의 흐름
  - 중단된 단계가 자동으로 다시 돌지 않는지, 이유가 있을 때만 이어 가는지, 다시 돈 단계 뒤 단계도 다시 도는지
  - 모델이 입력을 바꾸면 실패하는지, 원본 바이트가 바뀌면 모델 호출 전에 멈추는지
  - 러너 끝-끝: 앞 단계 → 생성 → 게시 payload를 서버 입장(로컬 경로 없는 요청)에서 다시 검증하고, 위변조 4종은 거절하는지
  - 관리자 이어 하기 이유가 전달되는지
  - 이전 생성기 경로가 map-tree 요청을 모델 호출 없이 거절하는지
- **로컬 재생 검사**: 사슬알균 시범 보관 응답(`runs/_e2e/26110901`, git 밖)을 가짜 Codex로 재생했다.
  - 다섯 단계 지시문이 시범과 같다.
  - 개념 지도와 최종 포인트가 시범 packet과 같다.
  - 대조 판정이 시범과 같다(지적 10 → 보완 뒤 6).
  - 보관본이 없는 CI에서는 건너뛴다.
- 전체 `tests/contracts`·`tests/quizbank`·`tests/runner`: 1,614 통과. 1개 제외(`test_desktop_control` 한글 바로가기, 기존 결함).
- 서버 `-m tests root`: 27 통과.
- 공개된 두 결과(26110803, 26110901)는 바뀐 `validate_result`·`validate_all`을 그대로 통과한다.
- 모델 호출·운영 DB 쓰기: 없음

### 남은 것 (PR C 이후)
- 서버가 map-tree 요청을 만드는 일. `RequestIn.pipeline`, 이미 공개된 강의 거절, `privatePilot` 기본값 false, 이어 하기 이유 전달이 여기 든다.
- 관리자 화면 기본값과 승인 문구.
- 러너 배포 사본 갱신.
- 서버 jokbo Asset 바이트가 시범 PDF와 같은지 읽기 전용으로 대조하는 일. PR C 시작 때 한다.

## 배포 대상 버전·순서·데이터 변경
- PR B 병합은 API를 자동 배포한다.
  - 서버는 계약의 `validate_result`를 쓰므로 map-tree 결과를 검증할 수 있게 된다.
  - 그러나 map-tree 요청을 만드는 경로는 PR C 전까지 없다. 기존 요청의 동작은 바뀌지 않는다.
- DB 스키마 변경과 데이터 변경은 없다.
- 러너 배포 사본은 병합으로 바뀌지 않는다.

## 배포 후 확인·롤백·필요한 사람 승인
- 확인: 배포된 API revision이 병합 SHA인지 본다.
- 롤백: git revert. map-tree 요청이 아직 없으므로 되돌릴 데이터가 없다.
- 사람 승인: 이 PR에는 「사람에게 묻는 것」에 닿는 일이 없다.
