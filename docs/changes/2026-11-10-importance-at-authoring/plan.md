# Main-Quiz 중요도를 출제 단계로 · 포인트는 누락 점검표로 — 구현 계획

spec R1–R8을 PR 세 개로 나눈다. 순서는 A → B → C다. 각 PR은 앞 PR이 master에 병합된 뒤 최신 master에서 만든 브랜치로 작업한다.
- A는 순수 계약이다.
- B는 생성기와 지시문이다. 러너가 실제로 쓰는 경로이므로, B가 병합되면 새 생성 요청부터 /4로 돈다.
- C는 서버 학습이다.

**B와 C의 병합 순서:** /4 문서가 운영 DB에 들어가기 전에 C가 배포되어 있어야 한다. 그렇지 않으면 늘어난 과제가 일정에 오르지 않는다. 그래서 B는 /4 생성기를 관리자 「새 구조(시범)」 요청에서만 켜고, 결과의 반입·공개는 C 배포 뒤에만 한다(별도 승인).

## 변경 범위·대상 파일·순서

### PR A — 계약 (`studyez_contracts`, 모델·DB·서버 없음)
1. `studyez_contracts/bank/importance.py`
   - 문항 단위 계산을 더한다: `question_table(questions, profile)`, 문항 basis 기반 `target_axes`.
   - 기존 `point_table`·`question_decision`은 /3 결과를 읽기 위해 남긴다.
2. `studyez_contracts/roots/generation_v3.py`에 `/4` 갈래를 둔다(새 파일 `generation_v4.py`로 분리하는 편이 작으면 그렇게 한다).
   - **R1:** POINT 스키마에서 `importance_basis`를 뺀 /4 형태. `_check_point`의 /4 판도 같이 만든다.
   - **R3:** `map_check_input`에서 importance를 뺀다.
   - **R5:**
     - `check_coverage`·`covering`·`not_ready`를 component 합집합 규칙으로 바꾼다.
     - 커버리지 출력에 `duplicates`를 더하고 검사한다(묶음 안의 문항이 같은 방향의 evidence에 있는지).
     - `add_input`은 빠진 component만 넣는다.
   - **R6·R7:** 새 조립 `make_document_v4`.
     - 과제 = verdict ok·의학 ok·중복 대표인 모든 문항.
     - `direction_id`는 answer component가 가장 많은 방향.
     - target·scope·relation·visual 판정은 과제 여부에 쓰지 않는다.
     - `order_plan` 재사용, `mergedDuplicates`·`unplacedQuestions` 기록.
   - **R7:** `readiness`를 방향 커버리지 보고로 바꾼다.
   - **R2:** 문항 basis 형식 검사, 출력 형식 오류 처리. `intake_projection`·`project_importance`의 /4 판(문항 basis로 계산).
   - **R3:** 문항 검토 출력에 선택 필드 `importance_notes`. 결정에 쓰이지 않는다.
3. `studyez_contracts/roots/validate.py`
   - **R8:** `generation_policy == 'root-generation/4'`이면 "과제 문항이 방향의 component를 하나 이상 answer로 묻는다"를 요구한다. 그 외 정책은 현행 규칙을 쓴다.
   - /4의 판 사이 승계 키를 문항 지문으로 한다(`learning_links` 지문 함수 재사용).
4. `studyez_contracts/roots/automation.py` `validate_result`: 정책 이름으로 /4 갈래.
5. 검사: `tests/contracts/test_generation_v4.py`(새).
   - spec R2·R3·R5·R6·R7 수용 항목을 고정 입력으로 확인한다.
   - 261102_02 상황을 줄인 고정물을 쓴다: D001에 Q001·Q002·Q003, T020 target conflict, Q012 그림 없음, Q088 component 일부만.
   - 기존 `test_generation_v2.py`·`test_generation_v3.py`·`test_roots.py`·`test_importance_basis.py`는 바뀌지 않은 채 통과해야 한다.

### PR B — 생성기·지시문 (러너 경로)
1. 앞 단계(`runner/root_front.py`)
   - /4이면 point 스키마를 `point-output-v4.schema.json`(새, basis 없음)로 하고 `point-extract-v4.md`(새)를 쓴다.
   - `map-tree/point-audit.md`·`point-repair.md`에서 중요도 근거 확인 항목을 /4일 때 뺀다. 지시문을 /4 사본으로 나눌지는 기존 파일의 분기 방식을 따른다.
   - `map-tree/bank-task.md`에 문항별 `importance_basis` 작성 지시를 넣고, kind 표는 `importance.py`에서 생성한다.
2. `content/prompts/learning-links/v3/`의 /4 판
   - `coverage.md`: 합집합 규칙, `duplicates` 기준(spec R6). "부분 사실의 합집합으로 대신하지 않는다" 삭제.
   - `add.md`: 빠진 component만, 문항 basis.
   - `fix.md`: 내용을 바꿀 때만 basis 수정.
   - `map-check.md`: 중요도 근거 확인 삭제.
   - `item-review.md`: `importance_notes`(판정 아님).
   - `point-supplement.md`: basis 없음.
3. `quizbank/connection_generate_v3.py`
   - 패킷의 정책이 /4이면 위 계약과 지시문을 쓰고, 조립은 `make_document_v4`.
   - manifest에 `importanceProjection`(문항 기준)·`mergedDuplicates`·`unplacedQuestions`·`importanceNotes`를 남긴다.
4. 요청 경로: 관리자 「새 구조(시범)」 요청(`map-tree/2`)에 /4 선택을 더한다. 기본값은 지금 그대로다(/3).
   - 서버 `routes/root_generation.py`의 패킷 정책 필드와 웹 관리자 버튼에 해당한다. 화면 변경은 선택지 하나다.
5. 러너 재설치 절차는 메모리의 「러너 새 코드 반영 절차」를 따른다.
6. 검사: `tests/quizbank/test_root_generation_v4.py`(새). 가짜 모델 출력으로 /4 전 단계를 통과하는지 확인한다. 기존 v3 검사는 유지한다.

### PR C — 서버 학습 (과제 단위 상태)
> 겹침: 대시보드 P0 「Main-Quiz 풀이 지연」(claude/main-quiz-latency, PR #28)이 `routes/root_learning.py`·`root_learning/content.py`를 고치는 중이다. C는 #28이 병합된 뒤 최신 master에서 시작한다.
1. `server/app/root_learning/state.py`: /4 문서는 task_id 단위로 재생한다. 방향 값은 과제 값에서 계산한다(spec R8). /3 이하는 기존 함수를 쓴다.
2. `server/app/root_learning/planning.py`: /4는 방향마다 첫 과제만 고르지 않는다. 예정 과제를 모두 후보로 하고, 선행·지도 순서로 배치한다.
3. `server/app/routes/root_learning.py` `prior_exposure`: /4는 같은 task_id만 센다.
4. `server/app/root_learning/content.py`: /4 판 사이 승계는 문항 지문 기준이다.
5. `generation_v2.py:737-751`의 문항→첫 과제 연결 함수가 여러 과제를 처리하도록 고친다(KeyError 방지).
6. DB 스키마·기존 이벤트는 바꾸지 않는다.
7. 검사: `server/tests/test_root_learning_v4.py`(새, 격리 SQLite).
   - 과제 3개가 각각 일정에 오르는지, 평가 독립인지, 방향 recalled 조건, /3 재생 불변을 확인한다.
   - 웹은 바꿀 곳이 없다(조사 결과). typecheck·build로 확인한다.

## 검사 명령과 성공 조건
저장소 루트에서 실행하고 `scripts/development.py verify`로 기록한다. 서버는 `server/.venv`, 루트는 anaconda python(`PYTHONIOENCODING=utf-8`)을 쓴다.

| PR | 명령 | 성공 조건 |
|---|---|---|
| A | `python -m pytest tests/contracts -q` | 전부 통과. 새 v4 검사가 실제로 실행됨(수 확인). 기존 검사 수가 줄지 않음 |
| B | `python -m pytest tests/contracts tests/quizbank tests/runner -q` | 전부 통과. master에서도 실패하는 기존 결함은 따로 표시 |
| C | `server/.venv/Scripts/python.exe -m tests root_learning` 등 파일별 서버 검사, `npm --prefix web run typecheck`·`build` | 통과. 로컬 venv의 PyMuPDF 부재로 생기는 실패는 따로 표시 |
| 공통 | `bank-prompt.json`이 바뀌었으면 `git restore` | 커밋에 섞이지 않음 |

서버 검사는 격리된 로컬 DB만 쓴다. `server/.env`(운영 DB)를 쓰는 명령은 실행하지 않는다.

## 위험·복원·승인할 범위
- **이번 승인으로 하는 것:** PR A·B·C의 코드·지시문·검사 구현, 로컬 검사, PR 생성.
- **이번 승인에 포함되지 않는 것(각각 별도 승인):**
  - master 병합(= 자동 배포)
  - 러너 재설치
  - 실제 모델 시범(필기·족보의 OpenAI 전송 포함)
  - 261102_02 재생성
  - 운영 반입·학생 공개
  - 기존 판의 학습 기록 승계
- **위험 1:** 과제가 많아져 학생 분량이 늘어난다. 하루 할당은 목표 단위라 몰리지 않지만, 시범 판을 공개하기 전에 과제 수를 보고한다.
- **위험 2:** 중복 판정이 느슨하면 비슷한 문항이 여럿 남는다. 시범에서 `mergedDuplicates`와 남은 묶음을 표본 검토한다.
- **위험 3:** C 배포 전에 /4 문서가 공개되면 늘어난 과제가 일정에 오르지 않는다. B의 /4는 시범 요청에서만 켜고, 반입은 C 뒤에 한다.
- **복원:**
  - /4는 정책 이름으로 갈라지므로, 생성 요청의 기본값(/3)을 유지하는 한 기존 동작은 바뀌지 않는다.
  - 문제가 생기면 /4 선택을 끄면 된다. 이미 반입된 /4 판은 이전 활성 판으로 되돌린다(관리자 publication 경로). 학습 이벤트는 지우지 않는다.
- **보존:** 공개된 판과 학습 기록, 261102_02 기록(`runs/_root-generation/1c484a7b…`), 기존 수정 상한은 손대지 않는다.
