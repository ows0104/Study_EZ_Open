# Main-Quiz 생성 검수·수정 묶음 병렬화 — 배포 준비

## 코드 리뷰·검증 결과
- 새 검사 `tests/quizbank/test_root_batch_parallel.py` 9개(5회 반복 모두 통과):
  - 동시 실행 확인(검수·수정 단계가 2개 이상 동시에 돎), 결과가 순차 실행과 같음(단계 기록 차이는 수정 입력의 conflict_scope와 의학 검토 시각뿐)
  - 완료 순서를 바꿔도(지연 3가지) 결과·판정 기록·ledger 단계 순서가 같음
  - 한 묶음 실패 → 다른 묶음은 끝까지 돌고, 이어 만들기에서 완료 단계는 모델을 다시 부르지 않음
  - 선행 연결이 걸친 강의는 순차(이유 기록), 수정 입력에 범위 없음
  - 다른 묶음이 바꾼 중복 짝 → `v4-coverage-merge-0` 한 번
  - 묶음별 새 충돌 ID 접두어(`CF-B1-01`, `CF-B2-01`)로 합쳐짐, 범위 검사 단위 검사
  - `batchMode` 없는 이전 ledger는 순차·범위 없음·동시 호출 1
- 회귀(`development.py verify --check regression`): tests/quizbank·contracts·runner 2064 통과, 1 skip.
  제외 1개 `test_shortcut_installer_supports_korean_filename_in_windows_powershell`은 새 worktree에 `.venv`가 없어
  설치 스크립트가 넘어지는 환경 문제(변경과 무관). 중간 실행에서 Tk 창 검사 2개가 tk.tcl 로드 오류로 한 번 넘어졌고
  단독·재실행에서 통과(간헐 환경 문제).
- `ruff --select F821,F841,F811,F401` 변경 파일 통과.

## 배포 대상 버전·순서·데이터 변경
- 코드: quizbank(생성기 v3·v4, 묶음 실행기, 그림 잠금), studyez_contracts(수정 범위 검사), 지시문 v3/v4 fix.md 한 문단.
- 서버·웹·DB 변경 없음. 결과 manifest에 선택 항목 `batchPhases`가 더해진다.
- 순서: PR 검사 → master 병합 → 러너 재설치(메모리 「러너 새 코드 반영 절차」).
  병합·재설치는 진행 중인 /4 로컬 시범(대시보드 P1)이 끝난 뒤.

## 배포 후 확인·롤백·필요한 사람 승인
- 지시문 해시가 바뀌므로 이미 진행 중이던 /3·/4 실행을 새 러너로 이어 만들 때는 기존 규칙대로 이유(--resume) 한 번이 필요하다.
  완료 단계는 입력 지문이 같으면 재사용한다.
- 러너 ETA 통계(`runs/_stage_stats.jsonl`)는 `── ` 줄 사이 시간으로 재므로 동시 단계의 초가 실제보다 짧게 기록된다(표시용).
- 확인: 첫 실제 실행의 ledger `batchPhases`, 단계 시각(시작~끝), 결과 검증 통과.
- 롤백: 병합 되돌리기 + 이전 러너 설치본. 병렬로 만든 ledger(`batchMode`)를 이전 코드로 이어 만들면 이전 코드는 그 키를 무시하고 순차로 돈다. 범위 칸이 빠져 입력이 달라진 수정 단계는 기존 규칙대로(이유와 함께) 보관 후 다시 돈다.
- 사람 승인 필요: 실제 모델 재생(필기·족보 OpenAI 전송), master 병합 시점, 러너 재설치.
