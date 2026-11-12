# Main-Quiz 조립 검사: cloze 답 단위 수·접수 탈락 번호 재사용 — 배포 준비

## 코드 리뷰·검증 결과
- 회귀: `pytest tests/contracts tests/quizbank tests/runner` — 결과는 PR 본문과 state.json.
- 무모델 재생(실행 폴더 사본, 모델 호출은 예외를 던지게 함):
  - 수정 전 c45caf11 코드: 7c408043·f26a4f16이 원래 오류 그대로 멈춤, 모델 호출 요청 없음.
  - 수정 후: 7c408043·848efe1f는 `medical-0`(아직 안 돈 유일한 호출)까지 감. f26a4f16은 `medical-0`을 재사용해 끝까지 가고 result.json을 씀.
- 원인
  - 7c408043: 목표 D063의 Q124·Q125(`v4-add-0`이 쓴 표 cloze, 빈칸 8·저장 단위 4). `v4-coverage-1-0`이 본 앞면 기준으로 4~7을 적음.
  - f26a4f16: 접수에서 Q017·Q091·Q100 탈락 → `v4-add-0`이 Q100을 새로 씀(근거 `[]`) → 탈락한 Q100의 근거와 대조.
- 새 단위 검사는 추가하지 않았다(결과 전체 fixture가 필요). 재생이 검증이다.
- 독립 리뷰 없음(야간 긴급 수정, 원인 조사는 읽기 전용 하위 에이전트).

## 배포 대상 버전·순서·데이터 변경
- 병합 → master 검사 → API 배포 → 러너 `.runtime/main-quiz-<sha12>` 재설치(도는 `runner bank`가 끝난 뒤). DB·R2·웹 변경 없음.

## 배포 후 확인·롤백·필요한 사람 승인
- `/api/health` revision, 세 실행 이어 하기 뒤 게시 확인.
- 롤백: git revert, 이전 Cloud Run revision, 러너 `.runtime/main-quiz-76fc2f44f8f6`.
