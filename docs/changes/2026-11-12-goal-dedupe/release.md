# Main-Quiz 같은 문항 반복 제거 — 배포 준비

## 코드 리뷰·검증 결과

- 회귀: `pytest tests studyez_contracts` 2844 통과·4 건너뜀·1 제외(바로가기 설치기, 기존 결함). 리뷰 수정 뒤 `tests/quizbank tests/runner tests/contracts` 2183 통과.
- 서버: `-m tests root` 36개 중 34 통과. `test_root_map_tree`·`test_root_map_tree_v3`는 로컬 서버 venv에 PyMuPDF가 없어 import에서 실패(이 변경과 무관, CI에서 돈다). 기록된 server 검사는 `root_learning` 2개 파일이다.
- 피코르나 261111_02 게시 결과 무모델 재생: 판정 그대로 조립하면 게시 문서와 같다(과제 155). D077 세 문항을 묶음으로 넣으면 과제 153, D077 3→1.
  게시 문서의 첫날 회차에서 같은 방향 과제가 연달아 나오는 곳 31→0.
- 저장된 옛 실행(cf4d5917, 642fedef)의 단계 영수증이 새 코드의 `validate_all`을 통과한다.
- 독립 리뷰(읽기 전용 하위 에이전트)가 찾은 결함 2건을 고쳤다.
  1. 이미 묶인 두 문항에 세 번째 복사본이 오면 옛 묶음이 새 묶음을 밀어내 셋째가 과제로 남았다 → 새 묶음이 만나는 옛 묶음을 받아들인다.
  2. `ADD_OUTPUT` 최소 개수를 모든 /4 실행에서 바꿔, 이전에 끝난 추가 단계의 영수증 스키마 지문이 달라졌다 → 스키마를 단계 입력에서 정한다(`asked`가 있을 때만 빈 출력 허용).
- 리뷰가 남긴 낮은 위험(고치지 않음): 재확인이 다른 목표에 기존 문항의 첫 근거를 더할 수 있다. 묶음에서 남긴 문항이 다른 목표에 배치돼 있으면 그 목표의 과제가 0이 될 수 있다(readiness에 보인다).
- 확인하지 못한 것: 지시문 변경의 실제 모델 판정. 모델을 부르지 않았다.

## 배포 대상 버전·순서·데이터 변경

- PR 병합 → master 검사 → API → 웹 자동 배포. DB·결과 형식·서버 검증 규칙 변경 없음.
- 서버 배포 즉시 /4 문서의 회차 순서가 바뀐다(이미 공개된 강의 포함, 새로 만드는 회차부터).
- 러너: 병합 커밋으로 `.runtime/main-quiz-<sha12>` 설치 → 실행기·에이전트만 끄고 도는 `runner bank`는 끝까지 둠 → 다 끝나면 새 러너 시작.

## 배포 후 확인·롤백·필요한 사람 승인

- `/api/health` revision, 러너 `agent.lock` pid와 PYTHONPATH.
- 재설치 뒤 첫 강의: ledger `goalDuplicates`, `v4-add-*.input.json`의 `asked`, 재확인 입력의 문항 수, `mergedDuplicates`, readiness.
- 롤백: `git revert` PR, 이전 Cloud Run revision, 러너는 `.runtime/main-quiz-c45caf111ea6`.
- 승인: 사용자 2026-11-12 요청·「이어서 진행」. 공개 판 교체·재출제 없음.
