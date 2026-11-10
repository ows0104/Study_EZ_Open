# Main-Quiz 중요도를 출제 단계로 · 포인트는 누락 점검표로 — 설계

R1–R4는 중요도, R5–R8은 커버리지·과제·학습 상태(사용자 결정 D1·D2)다.
대상 경로: Main-Quiz 새 구조 `map-tree/2` → `root-generation/3`(새 실행은 `/4`)
- 주요 코드: `quizbank/connection_generate_v3.py`, `studyez_contracts/roots/generation_v3.py`, `generation_v2.py`의 importance 함수, `studyez_contracts/bank/importance.py`
- 단계 프롬프트: `content/prompts/learning-links/` 아래의 point·audit·map-check·author·add·fix

Quiz Bank(웹 `content/prompts/bank/bankPrompt.md`)와 Study Engine은 바꾸지 않는다.

## 요구사항과 수용 기준

### R1. 포인트는 중요도를 갖지 않는다
- 포인트 추출·보완·보충(point, point-repair, v3 point-supplement)의 POINT는 `{point, source_refs}`만 갖는다. `importance_basis`를 요구하지도, 출력하지도 않는다.
- 포인트 검수(audit, final-audit) 지시문에서 중요도 근거 확인 항목을 뺀다. 검수는 누락·과분할·범위·출처만 본다.
- 강의 단위 `notebook_profile`(`{legend, emphasis_style, reason}`)은 포인트 문서에 그대로 둔다. 문항 점수에서 `writer_mark`를 셀지 정할 때 필요하다.
- 수용: 새 실행의 exam-points에 `importance_basis`가 없고, 계약 검사가 통과한다.
  옛 실행의 포인트에 basis가 있으면 읽되(호환), 새 실행에서는 쓰지 않는다.

### R2. 문항이 근거를 적고, tier는 계산한다
- 처음 출제(bank), 추가 출제(v3-add), 문항 내용을 바꾸는 고치기(v3-fix)는 문항마다 `importance_basis`를 쓴다. 근거가 없으면 빈 배열로 둔다.
  - kind 표와 형식은 `importance.py`의 것을 그대로 쓴다(`KINDS`, `validate_basis`).
  - 부하를 줄이기 위해 `quote`는 `exam_forecast`·`exam_exclusion`에서만 원문을 요구한다(현행 규칙과 같다). 그 밖에는 빈 문자열을 허용한다.
  - `reason`은 한 줄로 쓴다.
- 저장 위치: 은행 3.3 문항 스키마는 추가 필드를 허용하지 않는다(`additionalProperties: false`).
  - 그래서 생성기는 저작 출력에서 문항별 basis를 떼어 낸다. basis는 결과 manifest `questionImportance`(question_id → basis)에 두고, 은행에는 넣지 않는다.
  - 은행 스키마는 바꾸지 않는다.
- 문항의 tier와 importance는 `score(문항 basis, notebook_profile.emphasis_style)`로 계산한다.
  - 저작이 적은 `tier`·`importance` 값은 조립 때 덮이며, 덮인 내역은 `importanceProjection`에 기록한다(현행 방식).
  - 포인트별 최댓값을 쓰던 `question_decision`은 새 실행에서 쓰지 않는다.
- 고치기가 문항 내용을 바꾸지 않으면 basis를 그대로 보존한다. 고치기가 basis만 바꾸는 것은 허용하지 않는다(R3).
- 개념 중요도는 그 개념 문항들의 최댓값으로 정한다(현행).
- 목표 3축(exam·clinical·structural)은 그 목표에 매핑된 문항들의 basis를 축별로 모아 정한다. 근거가 있으면 supported, 없으면 insufficient다.
  - 문항↔목표 연결은 `review.mappings`, 매핑이 없는 문항은 `point_ids`→`points[].target_ids`를 쓴다.
- 경고는 유지하되 문항 기준으로 잰다. Must-Know 비율 34% 초과, 같은 예고 원문의 여러 문항 반복. 둘 다 보고만 하며 문항을 막지 않는다.
- 수용: 고정 입력 테스트로 확인한다.
  - 문항 basis가 같으면 tier가 같다.
  - `exam_forecast`가 있는 문항은 Must-Know다.
  - basis 필드가 없는 문항(빈 배열과 구별)은 그 단계의 출력 형식 오류로 처리한다. 기존 재시도 규칙을 따르고, 새 재시도는 만들지 않는다.

### R3. 중요도는 아무것도 막지 않는다
- 지도 확인(map-check, C2m)의 입력에서 `importance_basis`를 뺀다. `target_checks`는 목표의 내용과 범위가 원본과 맞는지만 판정한다.
  - 지시문에서 "목표의 근거가 원본과 맞는가"의 중요도 부분을 삭제한다.
- 문항 검토(v3-review)는 basis가 원본과 다르다고 보면 `importance_notes`에 적을 수 있다.
  - 이 기록은 verdict, 수정 라운드, 과제 여부, readiness 어디에도 영향을 주지 않는다.
  - basis는 계산에 그대로 쓰고, 기록은 manifest에 남겨 관리자 화면에 보인다.
- 수용: 고정 입력 테스트로 확인한다. 같은 문항과 판정에서 basis만 틀리게 넣어도 `target_checks`, `doc.tasks`, `readiness`가 바뀌지 않는다.

### R4. 학생 화면과 기록
- 은행 3.3 형식, 5/4/3/2 importance, Study Engine 정책, 「내 중요도」(root_event kind=tier)를 바꾸지 않는다.
- 근거 화면(root_evidence의 족보·핵심 슬라이드)이 포인트 basis를 읽던 곳은 문항 basis를 읽게 한다. 해당하는 읽는 곳은 plan에서 확정한다.

## 책임·입출력 계약·오류 상태
| 단계 | 바뀌기 전 | 바뀐 뒤 |
|---|---|---|
| point / point-repair / supplement | 포인트와 근거 판정 | 포인트만(누락 점검표). notebook_profile 유지 |
| audit / final-audit | 누락·분할·범위 + 근거 라벨 검수 | 누락·분할·범위·출처 |
| bank / v3-add / v3-fix | 문항(tier는 표를 옮겨 적음) | 문항 + 문항별 basis |
| map-check | 목표 내용 + 목표 중요도 근거 | 목표 내용만 |
| v3-review | 문항 판정 | 문항 판정 + 선택 `importance_notes`(판정 아님) |
| 조립 | 포인트 표 → 문항 투영 | 문항 basis → 계산 → 투영 |

- 계약 표시: 새 실행은 정책 `root-generation/4`이고, 이것이 문항 기준 중요도를 뜻한다. `/3` 이하 결과는 포인트 기준 검증 경로로 읽는다(`validate_result`가 정책 이름으로 갈라 읽음).
- 오류: basis 형식 오류(kind 미상, refs 없음, 예고 원문 없음)는 그 단계 출력의 형식 오류다. 내용이 틀린 것은 오류가 아니라 `importance_notes`로 남긴다.

## 호환성과 데이터 보존
- 공개된 판(261105_01 map-tree-26110901, 261104_02 map-tree-26110803)과 그 학습 기록, 「내 중요도」 기록은 바꾸지 않는다.
- 261102_02의 현재 result.json과 `runs/_root-generation/1c484a7b…`는 보존한다. 새 방식으로 다시 생성하는 일은 사용자의 별도 승인 범위다. 이 경우 기존 수정 상한을 초기화하지 않는다.
- 옛 결과를 다시 검증해도 같은 값이 나온다(`importanceSource` 없음 → 현행 경로).
- `importance.py`의 kind 표, 가중치, 문턱, 34% 경고선은 그대로 둔다.

## 부하 추정 (261102_02 실측 기준)
- 빠지는 것:
  - 포인트 근거는 포인트 문서의 32–35%다(약 7–8천 자). point 단계 출력 8.1천 토큰 중 상당 부분이 여기에 해당한다.
  - 포인트 검수 지적 중 중요도 관련: audit 7건 중 4건, final-audit 3건 중 1건. 그만큼 point-repair 지시가 준다.
  - map-check 입력의 근거 표와 근거 쪽 PNG가 빠진다.
- 더해지는 것: 문항 134개 × 평균 약 0.8건 × (kind·쪽·한 줄 사유 약 60–80자) ≈ 7–10천 자. 출제 단계 출력(첫 출제 11.1천 토큰)의 대략 15–25%이며, 추가 출제와 고치기에 나누어 붙는다.
- 판정이 뒤집혀 목표가 막히거나 다시 고치는 라운드가 사라진다. 전체 모델 시간은 같거나 줄어들 것으로 본다.
- R5·R6의 영향:
  - 커버리지 출력에 `duplicates` 묶음이 더해진다(작음).
  - covered 기준이 느슨해져, "전체를 묻는 한 문항"을 만들려던 추가 출제가 줄어든다. 이번 실행에서는 추가 출제 54문항 중 과제가 된 것이 10개뿐이었다.
  - 모델이 아니라 학생 쪽 부하는 늘어난다. 과제가 46개에서 최대 약 120개(ok 문항 − 중복)로 늘 수 있다. 하루 분량은 목표 단위 할당량이 정하므로 하루에 몰리지는 않지만, 한 강의를 끝내는 데 필요한 문항 수는 늘어난다.
- 확인 방법: 구현 뒤 실제 모델 시범 한 편에서 단계별 usage를 이번 실행과 비교한다(별도 승인).

## 근거
- 실행: `runs/_root-generation/1c484a7beda3416bae8ee771d65ffcfc/generation/result.json`
  - 초기 문항 81(접수 거절 1 → 80), 추가 51 + 3 → 134
  - 회상 방향 71, 준비된 방향 49, 과제 49(고유 문항 46)
- 목표 conflict 4개(T015·T017·T020·TS2)의 사유는 모두 중요도 근거 라벨에 관한 것이다. `sourceAudit.assessment.issues` 중 map_fix 3건이 여기에 해당한다.
- 판정 뒤집힘: front/audit 지적은 "P026·P033 professor_remark → exam_forecast", source assessment 지적은 "exam_forecast → professor_remark"였다.

## 커버리지와 과제 (사용자 결정 D1·D2, 2026-11-10)

새 실행의 정책 이름은 `root-generation/4`로 한다. `/3` 이하 결과는 지금처럼 읽고 검증한다.

### R5. 커버리지: 어느 문항이든 묻기만 하면 인정 (D1)
- 커버리지 단계(v3-coverage)는 지금처럼 방향마다, 그리고 그 방향을 다루는 문항마다 component별 위치(answer·provided·explanation·missing·unknown)를 적는다.
- 판정 규칙을 바꾼다. 방향의 **모든 component가 적어도 한 문항에서 answer**이면 covered다. 한 문항이 전부를 회상할 필요는 없다(component 합집합).
  - `check_coverage`의 "covered needs one question that answers the whole goal"을 합집합 규칙으로 바꾼다.
  - 지시문 coverage.md의 "부분 사실의 합집합으로 종합 판단을 대신하지 않는다"를 삭제한다.
- missing은 "어느 문항도 답으로 묻지 않은 component가 있다"는 뜻이다. 추가 출제(v3-add)는 그 component만 채운다. 추가 횟수 상한(`ADD_LIMIT`)은 그대로 둔다.
- 그림이 필요한 방향(`requires_visual`)은 그림 자극이 있는 문항이 적어도 하나 그 방향의 component를 답으로 물어야 covered다. 그림 없는 문항(예: Q012)은 과제에서 빠지지 않는다. 그림 문항이 없다는 사실은 추가 출제 사유가 될 뿐이다.
- 수용: 고정 입력 테스트로 확인한다.
  - component 둘을 각각 다른 문항이 답으로 물으면 covered, 하나라도 아무도 묻지 않으면 missing이다.
  - missing일 때 추가 출제 입력에는 빠진 component만 들어간다.

### R6. 과제: 검수를 통과한 문항은 모두, 진짜 중복만 합친다 (D2)
- 과제 = 원본 대조 verdict `ok`이고 진짜 중복으로 합쳐지지 않은 **모든 문항**이다. 방향마다 첫 문항 하나만 붙이던 규칙(`make_document`의 `next(...)`)을 쓰지 않는다.
  - 의학 검토는 지금처럼 과제를 빼지 않는다(medical-final/1: 원본 충돌은 판정, 나머지는 「현재 의학」 해설).
- 각 과제의 `direction_id`는 그 문항이 answer로 묻는 component가 가장 많은 방향이다. 같으면 지도 순서상 앞의 방향을 쓴다.
  - 어느 방향의 component도 answer로 묻지 않는 문항은 지금처럼 목표 밖 문항 보충(point-supplement)으로 새 포인트·목표를 받은 뒤 그 방향에 붙는다.
  - 보충 뒤에도 방향이 없으면 과제로 만들지 않고 manifest `unplacedQuestions`에 이유와 함께 남긴다(모델 재시도는 하지 않는다).
- **진짜 중복 판정**: 커버리지 단계가 같은 방향의 문항들을 이미 함께 보므로, 그 출력에 `duplicates`(같은 내용을 형식만 바꿔 묻는 문항 묶음)를 추가한다. 새 모델 단계는 만들지 않는다.
  - 기준: 같은 정답 내용을 같은 방향으로 회상시키면서 발문·형식·보기 조합만 다른 경우다.
  - 다른 인자·다른 방향(정방향·역방향)·다른 구별·다른 적용은 중복이 아니다. 예: Q001 숙주 인자와 Q003 환경 인자는 중복이 아니다.
  - 묶음에서 과제로 남길 문항은 결정적으로 고른다. verdict가 모두 ok인 문항 중 importance가 높은 것, 같으면 ID가 앞선 것이다. 나머지는 문제은행에 남되 과제가 아니고, manifest `mergedDuplicates`에 기록한다.
- 순서와 선행 관계는 지금처럼 `order_plan`(문항 선행 + 목표 선행)으로 정한다. 선행 문항이 과제가 아니면 그 과제는 dependency로 빠진다(현행 규칙, 바꾸지 않음).
- 수용: 고정 입력 테스트로 확인한다.
  - 한 방향에 ok 문항 3개(중복 없음)이면 과제 3개다.
  - 그중 2개가 duplicates 묶음이면 과제 2개이고, `mergedDuplicates`에 1개가 남는다.

### R7. 지도 판정은 과제를 막지 않는다
- R3(중요도)과 같은 원리로, 목표 판정(target_checks), 방향 범위 판정(scope_status), 관계 판정(relation_checks), 그림 판정(visual_verdict)은 과제 여부를 정하지 않는다.
  - 이 판정들은 커버리지(무엇을 더 낼지), 지도 수정 기록, 관리자 화면에만 쓰인다.
- 과제 여부를 정하는 것은 문항 자체의 원본 대조 verdict, 진짜 중복, 선행 문항의 준비 여부뿐이다.
- 예외 하나: 공용 계약(learning_links)은 검토되지 않은 관계(relation_checks가 supported가 아님)를 tested로 연결하지 못하게 한다. 이 규칙은 유지한다.
  - 그런 관계만 묻는 문항은 그 방향에 연결되지 않고, 다른 연결도 없으면 `unplacedQuestions`에 남는다.
  - 261102_02에서는 관계 102개가 모두 supported라 영향이 없었다.
- 목표 선행 관계(prerequisites)는 순서에만 쓴다. 검토된 선행 관계 중 앞 목표에 과제가 있는 것만 순서에 반영한다. 뒤 목표의 과제를 빼지 않는다.
- `readiness`는 방향 단위의 커버리지 보고로 바꾼다. 방향마다 ready(과제가 하나 이상) 여부와 이유를 적는다. 이유는 component 미커버, 그림 문항 없음, 문항 판정 미통과 등이다.
- 수용: 고정 입력 테스트로 확인한다. target_checks를 conflict로, scope를 conflict로, visual을 doubt로 바꿔 넣어도 같은 문항의 과제 목록이 변하지 않는다.

### R8. 학습 기록·서버·화면
조사 결과(2026-11-10), 문서 형식은 이미 방향 하나에 과제 여럿을 허용한다(`validate.py`는 task_id만 고유로 요구). 막는 것은 서버다.
- `server/app/root_learning/planning.py:17-21`: 방향마다 첫 과제 하나만 일정에 올린다(`setdefault`). 이대로면 늘어난 과제는 한 번도 나오지 않는다.
- `state.py:44-67`: 학습 상태(평가·예정일·단계)를 방향마다 하나로 재생한다. 그 방향의 어느 문항을 평가해도 방향 전체가 평가된다.
- `routes/root_learning.py:519-523`(`prior_exposure`): 한 회차에서 같은 방향의 앞 과제가 관계를 보여 주면, 뒤 과제는 "도움 받음"으로 처리된다.
- `validate.py:87`: 과제의 문항이 그 방향 **전체**를 시험해야 한다. R5와 충돌한다.
- `validate.py:23`(`direction_hash`): 방향에 붙은 문항이 늘면 해시가 바뀌어, 이전 판의 학습 기록이 그 방향으로 이어지지 않는다.

R5에서는 방향 하나의 내용이 여러 문항에 나뉜다. 예: Q001 숙주 인자, Q003 환경 인자. 그러므로 방향 단위 상태를 유지하면 Q001 하나를 맞혀도 Q003이 묻는 내용까지 회상한 것으로 처리된다. 그래서 다음과 같이 바꾼다(**권장안 B**).
- **/4 문서의 학습 상태는 과제(문항) 단위다.**
  - 평가·예정일·단계는 task_id마다 따로 재생한다.
  - 방향의 회상 여부는 그 방향 과제가 모두 회상됐을 때 참이다. 방향의 예정일은 그 과제들 중 가장 이른 날이다.
  - 목표의 recalled·ready 계산(`state.py:73-92`)은 이 방향 값을 그대로 쓴다.
- **일정**(`planning.py`): /4 문서에서는 예정이 된 과제를 모두 후보로 둔다. 한 회차에 같은 방향의 과제가 둘 이상 들어가면 지도 순서대로 배치한다.
  - `prior_exposure`는 /4에서 같은 과제(task_id)의 노출만 센다. 같은 방향의 다른 문항은 다른 내용을 묻기 때문이다.
- **검증**(`validate.py:87`): /4 문서는 "과제 문항이 그 방향의 component를 하나 이상 answer로 묻는다"를 요구한다. /3 이하 문서는 기존의 전체 회상 규칙을 그대로 쓴다.
- **판 사이 학습 기록 승계**: /4 문서는 방향 해시 대신 **문항 내용 해시**(question fingerprint) 단위로 이어 준다. 같은 내용의 문항이면 기록을 잇고, 바뀐 문항은 새로 시작한다. 이것은 "ID만으로 학습도를 승계하지 않는다"는 원칙을 따른다.
- **옛 문서와 기록**: /3 이하 문서는 방향마다 과제가 하나이므로 과제 단위 재생과 방향 단위 재생의 결과가 같다. 그래도 /3 이하는 기존 코드 경로를 그대로 쓴다. 이벤트는 이미 task_id를 갖고 있어 이전(migration)이 필요 없고, DB 스키마도 바꾸지 않는다.
- **화면**: 웹의 `readyDirectionIds`, 목표 수 계산, 오늘 화면은 의미가 바뀌지 않는다. 과제 수가 늘면 "오늘 할 문항" 수가 늘 수 있다. 하루 목표량 계산(`newGoalQuota`)은 목표 단위라 그대로다.

대안 A(작은 변경, 권장하지 않음): 방향 단위 상태를 유지하고, 회차마다 그 방향 과제를 돌아가며 하나씩 낸다. 서버 변경은 `planning.py` 한 곳이다. 대신 한 문항만 맞혀도 방향 전체가 회상된 것으로 처리되어 R5와 맞지 않는다.

- 수용(B): 서버 격리 DB 테스트로 확인한다.
  - /4 문서에서 한 방향의 과제 3개는 각각 일정에 오른다. 하나를 평가해도 나머지 둘의 상태는 그대로다.
  - 방향은 셋 다 회상되어야 recalled다.
  - /3 문서의 기존 이벤트 재생 결과는 변경 전과 같다(기존 서버 테스트와 고정물로 확인).

### 기록 정리 (D3)
- 커버리지 판정이 문항별 component 위치만 결정에 쓰게 되므로, 사유 문장과 표시가 어긋나 생기던 일관성 문제는 결정에 영향을 주지 않는다. 예: D001 사유는 "통합 문항 없음"인데 표시는 "답에 있음"이었다.
- 사유 문장은 기록으로만 보존한다.
