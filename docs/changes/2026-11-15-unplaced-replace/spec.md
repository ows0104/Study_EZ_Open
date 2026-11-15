# Main-Quiz 지도에 못 붙은 문항 재배치 — 설계

## 요구사항과 수용 기준

### R1. 늦은 보충은 기존 포인트를 「중복」으로 고르지 않는다 (`quizbank/connection_generate_v4.py`)
- 늦은 보충(`supplement-late`)의 입력에서 기존 포인트 목록을 비운다(`points: []`). 판정은 새 포인트 또는 범위 밖뿐이다.
  검토까지 마친 뒤에도 기존 목표에 붙지 못한 문항이라, 「기존 포인트와 같다」는 판정은 배치에 쓸 수 없다(실측 근거: intent).
- 새 포인트는 지금처럼 supplement-normalize → 새 목표 → coverage-supplement → map-check-late → B 배치.
  역방향 문항은 원래 목표와 다른 새 목표가 된다(사용자: 역방향도 따로 공부할 가치).
- 첫 보충(2a, 검토 전)은 그대로 둔다. 프롬프트는 바꾸지 않는다(프롬프트 지문·이전 실행 재사용 보존).
- 늦은 보충의 범위 밖 판정은 지금처럼 문항을 offGoalQuestions로 뺀다(기존 2a와 같은 정책).
- 수용: 테스트 모델에서 늦은 보충 입력의 points가 비어 있고, duplicate_of를 낸 응답은 검증에서 거절된다.

### R2. 재배치 실행 `unplaced-only/1` (중복 재판정 `duplicates-only/1`과 같은 틀)
- 요청: 관리자 요청 `restart + replacePublished + pipeline map-tree/3 + unplacedOnly: true` (서버 `root_generation.request`,
  duplicatesOnly와 같은 제약, 둘을 함께 켤 수 없음). packet에 `unplacedOnly: true`.
- 러너: duplicates_front처럼 앞 단계를 다시 돌리지 않고 공개된 실행의 derived packet을 쓴다.
  생성기를 `--unplaced-of <이전 generation 폴더>`로 부른다. 게시 뒤 근거는 이전 판 것을 새 판으로 올린다(reuse_evidence).
- 생성기(`quizbank/connection_replace.py` 새 파일):
  - 이전 실행의 단계 기록을 새 폴더로 연결(`connection_dedupe.seed`와 같은 검사: /4 실행·모든 단계 완료·게시 결과와 ledger 일치·
    강의 입력 같음·모델 같음).
  - ledger의 배치 정책을 `review-relations/2`로 올리고 `unplacedOnly` 기록(이전 판·이전 정책)을 남긴다.
  - 이어서 일반 /4 생성(`connection_generate_v4.run`)을 이유와 함께 이어 가기(resume)로 돌린다. 입력이 같은 단계는 기록을 쓰고,
    바뀐 단계만 모델을 부른다. 지도 관계 검사(A, brief-fix)는 하지 않는다: 공개된 지도를 바꾸면 모든 판정이 다시 돈다.
  - 결과는 일반 /4 결과(`validate_result`). manifest에 `unplacedOnly: {previousRevision, unplacedBefore, unplacedAfter, tasksBefore, tasksAfter}`.
- 수용: 테스트용 /1 실행을 재배치하면 새 모델 단계는 late 단계만, 기존 과제 전부 유지, 미배치 감소, A 단계 없음.

### R3. 관리자 화면·요청 도구
- 관리자 Main-Quiz 생성 패널에 duplicatesOnly 옆 「못 붙은 문항만 재배치」 요청(같은 확인 문구). 결과 보고는 기존 줄
  (범위 점검 판정·지도에 못 붙은 문항 목록)을 그대로 쓴다.

## 책임·입출력 계약·오류 상태
- 서버는 생성기를 import하지 않는다. 요청 검증과 packet 필드만 더한다(`unplacedOnly`).
- 이전 실행 폴더가 이 PC에 없거나 게시 결과와 다르면 멈춘다(중복 재판정과 같은 문구 체계). 실패는 실패로 보고한다.
- 재배치 중 의학 검토·맥락 판정 입력이 바뀌면(범위 밖으로 빠진 문항이 있을 때) 그 단계는 다시 돈다. 그 경우 보고에 남는다.

## 호환성과 데이터 보존
- 기존 문항·ID·검토 판정·의학 검토는 그대로 재사용한다. 이전 판 폴더는 읽기만 한다(하드 링크, 덮어쓰지 않음).
- 기존 /1 ledger로 이어 가는 다른 실행은 바뀌지 않는다(/1 회귀 검사 유지).
- 공개판 교체는 편마다 운영 요청 1건. 학습 기록은 기존 교체 재출제와 같은 규칙을 따른다(서버 변경 없음).

## R4. 결함 관계 수선 (2026-11-15 실측 뒤 추가, 사용자 「관계 수선 더해」)
- 근거: release.md 실측 — 피코르나 13개 중 1개만 붙음. 못 붙은 문항이 지도 점검 `unknown`·`conflict` 관계(주어·조건 누락)에 묶인다.
- 재배치(`unplaced-only/1`)에서 범위 점검 판정 배치(B) 뒤, 늦은 보충 전에:
  1. 지도 점검이 `unknown`·`conflict`로 둔 관계를 모아 기존 지도 구조 교정 단계(`v4-brief-fix-late`, brief-fix 프롬프트 그대로)에
     보낸다. errors 한 줄 = 관계 ID·현재 관계·지도 점검 판정과 이유, 「원본에 맞게 끝점·condition을 고쳐라, 관계 ID·목표·방향·포인트는
     바꾸지 마라」. 프롬프트를 새로 만들지 않는다(프롬프트 지문 보존).
  2. 코드 검사: 바뀐 것은 그 결함 관계(같은 ID)와, 새 개념 추가, 그 결함 관계에만 쓰이는 기존 개념뿐이어야 한다. 목표·방향·포인트·
     선행·출처·범위가 바뀌면 거절한다. 결함 관계에는 과제가 없으므로(지지되지 않은 관계는 과제를 받지 않는다) 기존 과제는 그대로다.
  3. 실제로 바뀐 관계만 지도 점검을 다시 한다(`v4-map-check-fix-late`, 그 관계를 쓰는 목표 입력). 새 판정이 그 관계의 이전 판정을
     대신한다. 바뀌지 않은 관계는 이전 판정 그대로(다시 뽑기 하지 않는다).
  4. 다시 조립(B) → 남은 문항은 늦은 보충(R1)으로. 늦은 보충의 새 목표가 고친 관계를 다시 쓰면 고친 판정이 적용된다.
- 문항 검토·범위 점검 판정은 다시 하지 않는다(문항·근거는 같고, 관계 문구만 원본에 맞게 구체화된다).
- 수용: 테스트 모델에서 unknown 관계에 묶인 문항이 수선 뒤 과제가 되고, 목표를 바꾸는 수선은 거절된다.
