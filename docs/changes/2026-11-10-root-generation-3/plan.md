# Main-Quiz 새 출제 구조 root-generation/3 — 구현 계획

[spec.md](spec.md)를 구현한다. 기준은 master cb0f7e5b다. 사용자 요청: 2026-11-10 「plan 써줘」(앞서 「spec 써줘」).

## spec 미정 사항의 기본값 (시범 뒤 다시 본다)

| | 기본값 | 이유 |
|---|---|---|
| U1 목표 밖 문항 | **정했다**(사용자 2026-11-10): 놓친 출제 포인트를 기존과 같은 형식으로 보충하고, 같은 점수표로 등급을 매겨 목표로 만든다(spec R2a). 범위 밖 문항만 과제에서 빼고 `manifest.offGoalQuestions`에 남긴다 | — |
| U2 묶음 크기 | 커버 확인: 목표 60개까지 한 호출(입력에 쪽 그림이 없어 가볍다)<br>문항 검토: 40문항 | 시험에서 47문항은 성공했고 149문항은 실패했다 |
| U3 근거 쪽만 넘기는 위험 | 시범에서 "근거 부족"으로 doubt·unknown이 된 판정을 세어 release에 적는다 | 실측 전에는 판단할 수 없다 |
| U4 기타 unknown 4개 | /3 커버 판정은 문항 판정과 떨어져 있으니 다시 생기는지만 본다 | — |

## 변경 범위·대상 파일·순서

PR 셋으로 나눈다. 각 PR은 혼자서 검사가 통과하고 /2 동작을 바꾸지 않는다. 순서는 A → B → C다.

### PR A — 계약 (`studyez_contracts`, 모델·DB 없음)
- **새 파일 `studyez_contracts/roots/generation_v3.py`**
  - 출력 스키마
    - `COVERAGE_OUTPUT`: 목표마다 status, question_ids, components, reason
    - `SUPPLEMENT_OUTPUT`: 목표 밖 문항마다 point·out_of_scope·duplicate_of 중 하나
      - point 칸은 `point-output-v3.schema.json`의 포인트 항목을 그대로 가져다 쓴다(형식을 새로 만들지 않는다).
    - `ADD_OUTPUT`: 새 문항, 새 문항의 visual_stimuli, 새 clinical_conflicts
    - `ITEM_REVIEW_OUTPUT`: 문항마다 verdict, checks, note, fix
    - `FIX_OUTPUT`: 대상 ID의 교체본
  - 포인트 보충 붙이기 `attach_points(points_doc, rows)`
    - 새 포인트에 다음 P번호와 `origin: question`·출발 문항 ID를 붙인다.
    - `importance.validate_basis`로 근거 형식을 확인한다.
    - 등급은 `importance.point_table`로 기존 포인트와 함께 다시 계산한다. 기존 포인트 등급이 그대로인지도 확인한다.
  - 새 포인트 목표 붙이기 `attach_goals(brief, new_targets)`
    - 기존 칸 투영 해시가 같은지 확인한다.
    - 합친 brief가 `validate_brief`를 통과해야 한다.
  - 입력 만들기(순수 함수): `coverage_input`, `supplement_input`, `add_input`, `review_input`, `fix_input`
    - spec 「입력 계약」의 칸만 만든다.
    - 쪽 고르기 `cited_pages(items, brief)`: `source_refs`·목표 `evidence`의 물리 쪽을 모은다.
  - 합치기·막기
    - `merge_added(bank, added, allowed_ids)`: 기존 문항 해시가 같은지, ID가 허락 범위 안인지 본다.
    - `merge_fixes(bank, fixes, targets)`: 대상 밖 ID를 거절하고, `question_id`·`concept_id`·`point_ids`가 유지됐는지 본다.
    - `worse(before, after)`: 판정 악화 여부. 되돌릴지 정한다.
  - 판정 장부: `question_hash`(기존 `source_assessment.question_hash` 재사용), 커버 키 `(direction_id, question_hash)`, 장부 검증.
  - 판정 포기: 커버 묶음의 목표가 전부 unknown이거나 검토 묶음의 판정이 전부 doubt면 `UNPERFORMED`.
  - 조립 어댑터 `assessment_raw` (spec R2m, 구현 중 추가)
    - /3 판정만 모아 `source-assessment/2`를 만든다. 빠진 판정은 거절한다.
    - 그 뒤 /2 `compile_assessment`·`make_document`를 그대로 쓴다.
    - 지도 확인 출력 `MAP_CHECK_OUTPUT`과 검사 `check_map`
  - `validate_result(result, packet)` — PR A 범위
    - 산출물 집합, manifest 칸, 장부 해시, 3단계 횟수(≤2), `medicalFinal`
    - 추가 전용: 처음 문항이 고치기 대상이 아니면 내용이 같다
    - 범위 밖 문항과 「준비 안 됨」 목표는 과제가 아니다
    - `sourceAudit`가 모은 판정의 /2 compile과 같다
    - 단계별 증거 사슬(입력·출력 해시)과 문서 재조립 비교는 단계 이름이 정해지는 PR B에서 더한다.
  - 공용 계약은 표준 라이브러리만 쓴다(`studyez_contracts/CLAUDE.md`).
    - 모델용 JSON Schema(anyOf 등)는 상수로만 두고, 검사는 `validate_shape`와 직접 확인으로 한다.
    - 보충 포인트 형식은 `point-output-v3.schema.json`과 같은지 테스트가 확인한다.
- **수정 `studyez_contracts/roots/automation.py` `validate_result`**
  - `pipelineVersion`이 `root-generation/3`인 결과를 v3 검증으로 보낸다.
  - /2·map-tree/1 갈래는 그대로 둔다.
- **새 파일 `tests/contracts/test_generation_v3.py`**: 입력 계약 칸, 합치기 거절, 되돌리기, 장부 재사용, 판정 포기, 결과 검증(통과 1 + 위조 거절 여러 개).

### PR B — 생성기·프롬프트·실행 어댑터
- **새 프롬프트 `content/prompts/learning-links/v3/`**
  - `coverage.md`, `map-check.md`, `point-supplement.md`, `add.md`, `item-review.md`, `fix.md`
  - `point-supplement.md`: 포인트·근거 종류의 정의는 `point-extract-v3.md`에서 그대로 옮긴다. 새로 쓰는 것은 「이 문항이 묻는 내용」으로 범위를 좁히는 문장뿐이다.
  - 새 포인트를 목표로 바꾸는 일은 정리 단계 프롬프트(`extract-v2.md`)를 새 포인트만 넣어 다시 쓴다.
  - 판정 원칙 문장은 `source-v2.md`·`author-v2.md`의 현행 규칙(정답 단위·회상 범위·문항 품질)에서 해당 부분만 옮긴다.
  - `add.md`·`fix.md`에는 지도 변경 권고를 넣지 않는다.
  - 새 정책 문구를 지어내지 않는다. 옮긴 출처를 `PROVENANCE.md`에 적는다.
- **새 파일 `quizbank/connection_generate_v3.py`** — 순서 제어
  - 1c 문제은행(+ 웹 응답이면 그대로)
    - 형식 오류는 같은 세션에 한 번 돌려보낸다. 그래도 깨진 문항은 `rejectedAtIntake`에 남긴다.
  - normalize: /2 단계 재사용
  - 코드 합치기
  - 커버 확인
  - 지도 확인(R2m), 새 목표가 생기면 그 목표만 한 번 더
  - 목표 밖 문항 → 포인트 보충 → 새 포인트만 목표로(R2a)
  - 추가 출제 + 좁힌 확인 ≤2
  - 코드 검사
  - 묶음 검토 → 보완 → 고친 문항 재검토(+그 목표 재확인) ≤2/문항
  - 임상 정리 확인: /2 `context` 단계를 한 번
  - 의학 검토: /2의 `medical-final/1` 호출 함수 재사용
  - 조립
  - ledger·재개: /2의 stage-resume/1 규칙을 같은 모양으로 둔다. 파이프라인 판 값은 `root-generation/3`이다.
- **수정 `runner/root_native_json.py`** — 추가만 한다
  - v3 단계 이름(`v3-coverage-n`, `v3-map-check`, `v3-supplement`, `v3-supplement-normalize`, `v3-add-n`, `v3-review-b`, `v3-fix-b-k`)의 스키마·프롬프트·`check_file` 갈래
  - `review_images`가 v3 단계에서는 입력에 적힌 쪽 그림만 붙이게 한다.
  - /2 단계 이름의 동작은 바꾸지 않는다.
- **테스트**
  - 새 파일 `tests/quizbank/test_root_generation_v3.py`: 가짜 모델로 끝까지 도는 검사
    - spec R0–R6 수용 기준 전부
    - 단계별 입력 칸 이름 검사
    - 추가 출제가 기존 문항·지도를 내면 거절
    - doubt가 커버를 바꾸지 않음
    - 목표 밖 문항에서 보충 포인트가 생기고, 같은 점수표로 등급이 매겨지며(Essential·Core·Optional 각각), 기존 포인트·목표는 그대로임. 범위 밖 문항은 과제에 없음
    - 최초 출제 문항 전부가 묶음 검토를 한 번씩 거침
    - 상한 뒤에도 wrong인 문항만으로 커버되던 목표는 「준비 안 됨(문항 결함)」
    - 같은 해시는 재검토 안 함
    - 악화 시 되돌림
    - 3단계 상한 2와 「준비 안 됨」
    - 재개가 상한을 초기화하지 않음
  - `tests/runner/test_root_native_json.py`: v3 단계 이름의 스키마·첨부 그림 검사를 추가한다.

### PR C — 요청 경로 (관리자 버튼 → 러너 → 서버)
- **`studyez_contracts/roots/map_tree.py`**
  - 새 pipeline 값 `map-tree/2`(map-tree 앞 단계 + 1c 문제은행 + /3)와 그 packet 형식 값을 추가한다.
  - 예전 러너는 모르는 형식을 모델 호출 전에 거절한다.
- **`runner/root_front.py`**: map-tree/2일 때 1c 문제은행 작업을 지도·포인트와 동시에 돌린다(`connection_parallel.model_job('bank', …)` 재사용). 1b 남은 지적을 `auditOpen`으로 넘긴다.
- **`runner/connection_generation.py`**: map-tree/2면 `connection_generate_v3`(어댑터 `root_native_json`)로 보낸다.
- **`server/app/routes/root_generation.py`**: `pipeline: Literal['map-tree/1','map-tree/2']`. 나머지 검사·공개 경로는 그대로다. DB 스키마 변경은 없다.
- **`web/src/bank/RootGenerationPanel.tsx`**
  - 「새 구조(시범)」 선택지로 map-tree/2를 추가한다. 기본값은 map-tree/1 그대로다.
  - 버튼 옆 승인 문구(보내는 자료·호출 상한)를 /3 상한으로 보인다.
- **테스트**
  - `server/tests/test_root_map_tree.py`에 map-tree/2 요청·거절·결과 검증 추가
  - `tests/runner/test_root_front.py`에 bank 동시 실행·auditOpen 추가
  - 웹 `tests/main-quiz-generation-button.test.cjs`에 선택지 추가

### 시범 (PR C 병합·러너 재설치 뒤)
- 사슬알균은 이미 학생에게 공개돼 새 요청이 409로 막힌다. 그래서 같은 고정 원본으로 로컬 실행한다.
  - 스크립트: `docs/changes/2026-11-10-root-generation-3/pilot.py`
  - 결과 폴더: `runs/_e2e/26110901/generation-v3`
- **이 실행은 사람에게 묻는 일이다.** 정해진 자동 경로 밖에서 강의 자료를 외부 모델로 보내기 때문이다. 시작 전에 보내는 자료·호출 상한을 적어 승인을 받는다.
- 다른 길도 있다. 아직 공개 전인 다음 강의에서 관리자 버튼(map-tree/2)을 누르는 것이다. 이때는 클릭이 그 강의의 승인이다.
- 비교 대상: generation-4(79/119 ready, 회귀 4), 추가 전용 시험(77/119 confirmed)
- 비교 항목: 단계별 입력 크기, 시간, 회귀 수, 재판정 수

## 검사 명령과 성공 조건

저장소 루트에서 루트 venv로 실행하고, `scripts/development.py verify`로 기록한다.

| PR | 명령 | 성공 조건 |
|---|---|---|
| A | `python -m pytest tests/contracts -q` | 전부 통과. /2 검사 수가 줄지 않는다 |
| B | `python -m pytest tests/contracts tests/quizbank tests/runner -q` | 전부 통과. 단 `test_desktop_control` 1개는 master에서도 실패하는 기존 결함으로 기록한다 |
| C | `cd server; python -m pytest tests -q`, 웹 `npm run typecheck`·`npm run build`·`node --test tests/main-quiz-generation-button.test.cjs` | 서버 root 검사 통과(서버 venv에 pymupdf가 없어 생기는 실패는 따로 표시). 웹 통과 |
| 공통 | `bank-prompt.json`이 바뀌었으면 `git restore` | 커밋에 섞이지 않는다 |

- **/2 회귀 기준**: `tests/quizbank/test_root_speed.py`, `test_root_resume.py`, `test_medical_final.py`, `tests/runner/test_root_native_json.py`가 바뀌지 않은 채 통과한다.
- **시범 성공 조건**: intent 성공 기준 1–4.

## 위험·복원·승인할 범위

**위험**
- **어댑터 공유**: v3 단계를 `root_native_json.py`에 더하므로 /2 동작이 바뀔 위험이 있다. 갈래를 단계 이름으로만 나누고, /2 어댑터 검사를 그대로 돌린다.
- **새 프롬프트의 판정 기준 변화**: 옮긴 문장이 원래와 다르게 읽힐 수 있다. 출처를 기록하고, 시범에서 /2 판정과 나란히 본다.
- **근거 쪽만 넘기기(U3)**: 판정이 근거 부족으로 흔들릴 수 있다. 시범에서 센다. 많으면 근거 쪽 앞뒤 1쪽을 더하는 쪽으로 바꾼다.
- **러너 설치본**: 병합해도 러너 사본은 바뀌지 않는다. map-tree/2를 쓰려면 설치본을 다시 깔고 옛 pid를 끈 뒤 띄운다(메모리 「러너 새 코드 반영 절차」).

**복원**
- PR별로 git revert하고, 이전 Cloud Run revision·Pages로 되돌린다.
- /2·map-tree/1은 그대로라 되돌릴 데이터가 없다.
- map-tree/2로 공개된 판이 생겼다면 publication 경로에서 `enabled=false`로 닫는다. 판과 학습 기록은 지우지 않는다.

**승인 범위**
- **이 요청으로 진행하는 것**
  - PR A·B·C의 구현·검사·PR·병합(자동 배포 포함)
  - DB 스키마 변경 없음, 운영 데이터 쓰기 없음
- **따로 묻는 것**
  - 시범 실행(강의 자료 외부 전송)
  - 기본값을 map-tree/2로 바꾸는 것
  - 공개된 판(감염병리1, 사슬알균) 교체
  - 학생 공개
