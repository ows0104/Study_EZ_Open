# Main-Quiz 파이프라인 안정화·시간 단축 — 배포 준비

## 코드 리뷰·검증 결과
검사(2026-11-11, anaconda python, worktree `claude/pipeline-resilience`):
- 새 검사 `tests/runner/test_front_resilience.py` 11개, `tests/quizbank/test_pipeline_resilience.py` 10개,
  `tests/studyez_llm/test_execution.py` 추가 5개: 통과.
- 회귀 `pytest tests/quizbank tests/contracts tests/runner tests/studyez_llm tests/quizgen tests/development`: 2783 passed, 2 skipped, 1 deselected(5분 30초).
  제외 1개는 이 기계에서 이전 변경들도 제외해 온 `test_shortcut_installer_supports_korean_filename_in_windows_powershell`.
  master(#114 러너 상태 창)와 합친 뒤 같은 명령: 2788 passed, 2 skipped, 1 deselected(`state.json`에 기록).
- `ruff check --select F821,F841` (바꾼 파일): 지적 없음.
- `python scripts/map_numbers.py --check`: 의존 경계 정상.

자체 검토(독립 리뷰 아님):
- 경계: 단계 이름·입력·지시문·결과 형식 그대로. 서버가 보는 파생 packet 단계 행과 결과 manifest 키는 바뀌지 않음(검사로 확인).
- 앞 단계 동시 줄: `dirty`는 포인트 줄만 읽고 쓴다. 지도·문제은행의 재사용 여부는 줄이 시작하기 전에 정한다.
  「포인트를 다시 돌리면 대조도 다시」, 「문제은행 실패 뒤 재개는 문제은행만」을 검사로 고정.
- 되돌려주기: 한 번뿐이고 같은 세션이어야 하며 같은 검사를 다시 통과해야 한다. 거절된 원문 보존.
- transport-retry: CLI 세션 오류 + 네트워크 표지일 때만. 시간 초과·콘텐츠 거절·사용량 한도·검사 실패는 표지가 있어도 제외(검사).
- 동시 실행 한도: 파일 잠금 자리. 실패한 호출과 죽은 프로세스의 자리가 돌아옴(검사). 자리 대기는 호출 제한 시간 밖.

확인하지 못한 것(실제 모델 실행으로만 알 수 있음):
- 동시 6에서 계정 한도·속도 제한에 닿는지. 닿으면 `STUDYEZ_ROOT_WORKERS=3`(코드 변경 없이).
- 실제 Codex 세션에서 앞 단계 후속 호출(재개)의 동작 — 생성 단계와 같은 호출 방식이지만 앞 단계에서는 처음이다.
- 실제 단축 시간. 예상: 앞 단계 19~23분 → 약 15분, 검토 6묶음 38분 → 약 19분, 6묶음 강의 전체 약 95분 → 65분 안팎.

## 배포 대상 버전·순서·데이터 변경
- 러너·생성기 코드만. 서버·웹·DB·R2 변경 없음(master 병합이 API·웹을 자동 배포하지만 그 코드는 바뀌지 않는다).
- 순서: PR 병합 → 돌고 있는 강의가 끝난 뒤 러너 `.runtime` 재설치(기존 절차) → 다음 관리자 버튼 요청이 첫 실측.
- 이 변경 전에 시작해 멈춘 실행은 새 러너에서 관리자 재개(`--resume <이유>`)로 잇는다(코드 지문이 달라지는 기존 규칙).

## 배포 후 확인·롤백·필요한 사람 승인
- 확인(첫 실행의 `runs/_root-generation/<gid>`):
  - `front/audit/state.json`의 `startedAt`이 `front/bank/state.json` 완료(파일 시각)보다 앞선다.
  - `generation/v4-review-<b>-0.input.json`이 모든 묶음에서 같은 분에 생긴다(한 번에 돎).
  - 로그에 `Codex 동시 실행 한도(8) 대기`가 잦으면 한도가 병목이다. `네트워크 끊김:` 줄과 ledger `transportRetries`로 재실행을 센다.
  - `front/*/check-failure.json`이 있으면 되돌려주기가 일한 것이다. 같은 오류가 반복되면 그 검사나 지시문을 고친다.
- 롤백: 병합 되돌리기 + 러너 이전 설치본. 동시 실행 수만 되돌릴 때는 환경 변수.
- 사람 승인: 필요 없음(운영 DB·공개 범위·자료 전송 경로 불변). 러너 재설치 시점만 진행 중 강의와 맞춘다.
