# Main-Quiz 호출 시간 단축 — 배포 준비

## 코드 리뷰·검증 결과
검사(2026-11-11, anaconda python, worktree `claude/pipeline-overlap`, #115 위):
- 새 검사 `tests/quizbank/test_pipeline_overlap.py` 10개, `tests/runner/test_front_overlap.py` 12개: 통과.
- 회귀 `pytest tests/quizbank tests/contracts tests/runner tests/studyez_llm tests/quizgen tests/development`: REGRESSION_RESULT
- `ruff check --select F821,F841`: 이 변경이 건드린 파일에는 지적 없음(다른 파일의 기존 F841 4건은 그대로).
- `python scripts/map_numbers.py --check`: 의존 경계 정상.

자체 검토(독립 리뷰 아님):
- 인라인: 프롬프트만 바뀐다. 지시문 파일·작업 폴더 파일·영수증·호스트 검사는 그대로(시범 재현 검사가 `task.md` 글자 일치를 확인).
- early-call: 답은 입력 지문이 같을 때만 쓰인다. 쓰였을 때 ledger 단계 기록·결과가 차례에 부른 것과 같음을 검사로 고정
  (normalize 인계 뒤 러너 영수증 검증 `validate_all` 통과 포함).
- 실패 규칙: 미리 부른 호출의 실패는 차례에 같은 오류로 실패, 재개 없이는 다시 돌지 않음(검사). 네트워크 끊김만 예외(transport-retry).
- 동시성: 미리 부른 검토는 `material/` 자기 사본을 읽는다(추가 회차가 공용 폴더에 그림을 쓰는 동안 「원본 자료 변경」 검사에 걸리지 않게).
  ledger 변경은 잠금 안, `earlyCalls`는 단계 이름순.
- 앞 단계: `early_normalize`의 모든 예외를 안에서 처리한다. 앞 단계 성공·실패는 이 호출과 무관.

확인하지 못한 것(실제 모델 실행으로만 알 수 있음):
- 인라인 뒤 모델이 정말 파일 읽기를 생략하는지, 호출당 몇 초가 줄어드는지.
- 검토 첫 호출 겹치기가 전체 시간을 실제로 줄이는지(마지막 묶음의 사슬 길이에 달려 있다).

모델 없이 실제 자료로 확인한 것:
- 오늘 게시된 실제 실행 두 건을 기록된 단계 답으로 새 코드에 재생했다(모델 호출 없음, 임시 폴더에만 씀).
  - 261111_02(cf4d5917, 4묶음): 단계 입력 36개 전부 기록과 같은 지문, 결과 문서가 게시본과 동일, 검토 첫 호출 3개가 미리 시작돼 쓰임(`used: true`).
  - 261104_03(811c94da, 6묶음): 단계 입력 52개 전부 같은 지문, 결과 문서 동일, 검토 첫 호출 5개가 미리 시작돼 쓰임.
  - 02:43의 fa71412a는 그 뒤 master에서 검토 형식이 바뀌어(근거 쪽·관계) 지금 코드로는 재생 대상이 아니다.
- 실제 강의 PDF 두 개(261111_02의 고정 원본, 쪽 그림·텍스트 66개 파일)로 `prepare`를 두 번 돌려 결과가 바이트까지 같았다.
  앞 단계가 준비한 `generation/material`을 생성기가 다시 준비해도 normalize 영수증의 자료 지문이 맞는다.

## 배포 대상 버전·순서·데이터 변경
- 러너·생성기 + `studyez_contracts/roots/map_tree.py` 리팩터(서버가 import하지만 값은 같다). DB·R2·웹 변경 없음.
- 순서: #115 병합 → 이 PR 병합 → 돌고 있는 강의가 끝난 뒤 러너 재설치 → 다음 관리자 버튼 요청이 첫 실측.

## 배포 후 확인·롤백·필요한 사람 승인
- 확인(첫 실행의 `runs/_root-generation/<gid>`):
  - `generation/ledger.json`의 `earlyCalls`: `normalize`와 `v4-review-<b>-0`이 `used: true`인지. `used: false`가 반복되면 그 겹치기는 헛호출이니 끈다.
  - 로그의 `(앞 단계와 나란히 미리 시작)`·`(미리 시작)` 줄과 `입력이 달라져 쓰지 않고 다시 호출` 줄.
  - 세션 기록으로 왕복 수 재측정: 검토 호출의 명령 왕복이 6.6번에서 줄었는지, 호출 평균이 141초에서 줄었는지.
  - `generation/normalize.input.json` 시각이 앞 단계 끝과 거의 같고 그 단계가 즉시 완료되는지.
- 롤백: 병합 되돌리기 + 러너 이전 설치본. 그때 앞 단계만 끝나고 생성기가 시작 안 된 실행이 있으면
  `generation/.native/normalize`를 `.native/normalize.early`로 옮긴다(이전 코드는 그 자리를 새로 만들려 한다).
- 사람 승인: 필요 없음(운영 DB·공개 범위·자료 전송 경로 불변).
