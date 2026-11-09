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

### PR B 병합 보류
- PR #62의 CI 두 작업(「Tests and build」, 「Windows runner checks」)이 시작되지 않았다.
  - GitHub 표시: 「The job was not started because recent account payments have failed or your spending limit needs to be increased」
  - 코드 실패가 아니다. 로컬 검사는 모두 통과했다.
- master 병합이 곧 배포인데, 지금은 배포 워크플로도 같은 이유로 돌지 않는다. 그러면 master와 운영 API가 어긋난다. 그래서 병합하지 않았다.
- PR C는 PR B 브랜치 위(`claude/main-quiz-runner-server`)에서 진행했다.

## PR C — 서버·웹 (R1, R6 서버 쪽, R7)

사용자 2026-11-09 「병합하고 PR C」.

### 바뀐 것
- **서버 `root_generation.py`**
  - `RequestIn.pipeline: 'map-tree/1'`
    - CLI·원본 모드에서만 받는다. 병렬·웹·provided와 함께 오면 422.
    - 형식은 `source-assessment/2-map-tree/1`, 작업 단계 문구는 「Main-Quiz 앞 단계(개념 지도·포인트) 대기」다.
  - 이미 공개된 판(`RootControl.revision`)이 있는 강의는 409로 거절한다.
  - 올해 필기·족보가 PDF가 아니면 422.
  - 같은 요청 ID로 다시 보낼 때 `pipeline`이 다르면 409. `pipeline`은 같은 입력 판별(`generation_input`)에도 들어간다.
  - `resumeReason`: map-tree 요청을 이어 할 때 필수다(없으면 422). packet `operatorResumes`에 이유·시각·관리자를 쌓는다.
  - 관리자 응답에 `pipeline`, `sources`(id·kind·파일명), `operatorResumes` 개수를 더했다.
- **`prequiz_jobs.claimed_job`**: map-tree 요청에 `rootGenerationId`를 붙인다. 블럭 범위 예외는 기존 병렬 요청과 같다.
- **계약 `packet_hash`**: `operatorResumes`를 입력 지문에서 뺀다. 옛 packet에는 이 칸이 없어 해시가 그대로다.
  - `map_tree.derive_packet`도 이 칸을 생성 packet에 옮기지 않는다. 이어 해도 생성 입력이 바뀌지 않는다.
- **러너 `run_generation`**
  - packet의 `operatorResumes` 중 이 폴더에서 아직 쓰지 않은 최신 이유를 `--resume`으로 넘긴다.
  - 쓴 개수는 `operator-resumes.json`에 적는다. 그래서 같은 이유로 두 번 재개하지 않는다.
- **웹 `RootGenerationPanel`**
  - 기본은 「개념 지도·출제포인트부터」(map-tree), `privatePilot` 기본값은 false다.
  - 요청 전에 승인 문구를 보인다: 「이 버튼이 이 강의의 승인입니다」, 보내는 자료(S1·S2 PDF)·보내는 곳(OpenAI Codex CLI), 호출 상한, 예상 1~1.5시간, 「학생에게 바로 공개」, 공개된 강의 거절.
  - 요청 뒤에는 실제 보낸 파일명을 보인다.
  - map-tree 작업의 이어 하기는 이유 칸을 채워야 버튼이 열린다.
  - 옛 방식(병렬, 기존 지도)은 「설정·기존 지도 사용」 아래에 그대로 둔다.
  - 이어 하기는 원래 요청을 그대로 다시 보낸다. 고치는 중에 발견한 문제다: 예전 방식 작업에 map-tree 표시를 붙이면 서버가 「입력이 달라졌다」며 거절한다.
- **spec과의 차이**: 요청 전에 쪽수를 보이지 않는다. 서버가 PDF를 열지 않기 때문이고, 쪽수는 러너가 센다. spec R1에 반영했다.
- **문서**: `docs/development/README.md` 「사람에게 묻는 것」에 map-tree 버튼이 그 강의의 공개·전송 승인이라는 줄, `server/CLAUDE.md` 계약 줄.

### 열린 질문 확인: 서버 족보 파일
- 2026-11-01 족보 업로드 검증 기록(`docs/changes/2026-11-01-jokbo-professor-priority/upload-verification.json`, 메인 체크아웃)의 261105_01 항목은 다음과 같다.
  - 파일: `2026-S9-족보-김범준.pdf`
  - sha256: `25d1cf…2489`
  - 사슬알균 시범이 쓴 PDF의 sha256과 같다.
- 그 뒤 교체됐는지는 운영 DB를 읽지 않아 확인하지 않았다.
- 러너는 실행 때 서버가 고정한 sha와 받은 바이트를 대조하고, 다르면 모델 호출 전에 멈춘다.

### 검사
- 서버 새 `tests/test_root_map_tree.py`(격리 sqlite·로컬 저장소)
  - 요청과 거절: 조합 422, 공개 강의 409, MD 원본 422, 학생 403
  - 같은 입력 재사용, claim 결합
  - 러너 앞 단계 + 생성을 그 자리에서 실행하고 `PUT result`
    - 생성 packet 위조·누락은 422
    - 게시 결과: `allowed_users == []`, 다른 강의 공개 설정·Quiz Bank 불변, 이벤트 +1
  - 공개 뒤 새 요청 409
  - 이어 하기: 이유 없으면 422, 있으면 queued·`operatorResumes`·입력 지문 불변
- 러너 새 검사 1개: 서버에 저장된 이유를 다음 실행에 한 번만 쓰는지, 그 결과를 서버 packet(이유 포함)으로 검증해 통과하는지
- 웹 `tests/main-quiz-generation-button.test.cjs` 8개
  - 기본 map-tree, 승인 문구, 이유가 있어야 열리는 이어 하기, 옛 방식 선택, 옛 작업 이어 하기는 원래 요청 그대로
  - 이 파일은 패널이 이미 쓰던 `./pollChain`을 대체하지 않아 master에서도 깨져 있었다(CI에서는 돌지 않는다). 고쳤다.
- `web` typecheck·build 통과. `main-quiz-generation-browser.test.cjs`는 playwright가 없어 실행하지 못했다.
- 로컬 실행 방법: 서버 venv에 PyMuPDF가 없어서 루트 venv의 `pymupdf`·`fitz`만 복사해 PYTHONPATH에 붙여 돌렸다. CI는 한 환경에 루트·서버 의존성을 함께 설치한다.
- 브라우저 미리보기는 하지 않았다. 패널은 관리자 API가 필요한데, 운영 API(70f1fad5)는 아직 `pipeline`을 받지 않는다.
- 수치: contracts 279 · quizbank 577 · runner 759(1개 제외, 기존 결함) · web 단위 12 · server 전체 130(직접 실행)
- 서버 전체를 처음 돌렸을 때 2개가 실패했다(`test_root_generation_columns`, `test_root_generation_poll`). 관리자 응답에 새 필드 3개가 생겨, 고정해 둔 응답 사본과 달라졌기 때문이다. `sources`가 없는 테스트용 packet에서는 KeyError도 났다. 응답 사본에 새 필드를 더하고 `sources`가 없어도 되게 고쳤다.
- 서버 전체를 `scripts/development.py verify`로 돌리면 110개가 sqlalchemy의 `platform` 버전 해석 오류로 시작하지 못했다(코드와 무관, 두 번 재현). 같은 코드를 `server/`에서 직접 `-m tests`로 돌리면 130개 모두 통과한다. 그래서 server 체크는 state.json에 실패로 남아 있다. 기록 도구의 서버 실행 환경은 따로 고칠 일이다.

## 배포 대상 버전·순서·데이터 변경
- 순서: PR B(#62) 병합 → PR C 병합. 둘 다 API·웹을 자동 배포한다.
  - GitHub Actions 결제가 풀린 뒤라야 CI와 배포가 돈다.
- DB 스키마 변경과 데이터 변경은 없다. 새 칸은 기존 JSON 칸(`root_generation.packet`) 안에 들어간다.
- 러너 배포 사본은 병합으로 바뀌지 않는다.
  - map-tree 요청을 실제로 돌리려면 러너를 새 코드로 다시 띄워야 한다. 옛 pid를 직접 끈 뒤 `runtime.json`으로 확인한다.
  - 그 전에 요청이 들어오면 옛 러너는 모델 호출 전에 거절한다.

## 배포 후 확인·롤백·필요한 사람 승인
- 확인: 배포된 API revision과 Pages 자산이 병합 SHA인지 본다.
- 롤백: git revert와 이전 Cloud Run revision·Pages. 그 사이 map-tree로 공개된 판은 publication 경로에서 `enabled=false`로 닫는다. 판과 학습 기록은 지우지 않는다.
- 사람 승인: 첫 실제 실행은 사용자가 관리자 화면에서 강의를 골라 누를 때 한다. 그 클릭이 그 강의의 자료 전송·학생 공개 승인이다.
