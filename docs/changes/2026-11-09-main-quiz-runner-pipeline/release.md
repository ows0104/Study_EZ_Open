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

### 간헐 실패
<조사 중>

## 배포 대상 버전·순서·데이터 변경
- PR A 병합은 API를 자동 배포한다. 서버는 `validate_result`를 계약에서 가져오므로 정책 manifest를 이해하게 된다.
- DB 스키마 변경과 데이터 변경은 없다.
- 러너 배포 사본은 병합으로 바뀌지 않는다. 새 정책은 러너를 새 코드로 다시 띄운 뒤 시작하는 생성부터 적용된다.

## 배포 후 확인·롤백·필요한 사람 승인
- 확인: 배포된 API revision이 병합 SHA인지 본다.
- 롤백: git revert. 그 사이 새 정책으로 만든 결과가 없다면 되돌릴 데이터가 없다.
- 사람 승인: 이 PR에는 「사람에게 묻는 것」에 닿는 일이 없다.
