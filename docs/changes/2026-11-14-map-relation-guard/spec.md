# 명세

## A. 지도 관계 검사 (`studyez_contracts/roots/generation_v4.py` 새 함수 `relation_findings(brief)`)
- 「내용 관계」: `kind != 'classification'`인 관계. 계층 관계는 제공 Map의 parent_id 보존이라 회상 내용을 담지 않는다.
- 방향마다 내용 관계 묶음을 만든다. 묶음이 비었거나, 같은 묶음을 가진 방향이 4개 이상이면 그 방향이 결함이다.
  결함 문구는 방향 ID와 「이 방향이 회상시키는 원본 사실을 잇는 관계를 relation_ids에 추가하라 / 방향별로 나눠라」.
- normalize 뒤 `v2.brief_findings(brief) + v4.relation_findings(brief)`가 있으면 기존 `brief-fix` 1회(같은 단계·프롬프트·검증).
- brief-fix 뒤에도 결함이 방향의 10% 초과면 멈춘다(coverage·검토 호출 전).

## B. 살리기 1 — 범위 점검 판정으로 붙이기 (배치 규칙 `review-coverage`, 정책 `review-relations/2`)
- 검토가 어느 목표의 관계도 적지 않은 문항은, 범위 점검(coverage) 행 중 그 문항이 component를 **하나라도**
  `answer`로 묻는 행에서 범위 점검이 **적은** `tested_relation_ids`(그 방향의 관계인 것)를 주장으로 쓴다
  (`assessment_raw`, 이유 `v4 coverage judgment (fallback)`). 사용자 정정(2026-11-14 「일부만 답해도 붙일 수 있잖아」):
  전부 답함을 요구하지 않는다.
- 관계는 지어내지 않는다. 범위 점검이 관계를 적지 않은 문항(운영판 98개 중 25개)은 B로 붙지 않고 C로 간다.
  공용 계약 `validate_document`가 과제마다 기록된 판정의 tested 관계를 요구하기 때문이다.
- 회상 단위·방향 선택은 기존 검토 배치와 같다: 답한 단위만 남기고(`_answered_units`), 답한 component가 많은 방향, 지도 순서.
  검토가 붙인 문항은 그대로다(검토 관계가 있으면 B는 쓰지 않는다).
- manifest·readiness.json에 `coverageFallback: [{question_id, direction_id}]`. 서버 보고와 관리자 패널에 개수 한 줄.
- 기존 /1 ledger·게시판은 /1 규칙 그대로 재검증된다(`_placement4`).

## C. 살리기 2 — 늦은 보충 (`connection_generate_v4.py`, 문항 검토 직후·임상 정리 전, 1회)
- 대상: 같은 조립을 임시로 돌려(`provisional_unplaced`, 임상 정리 칸만 임시값) 남는 문항 중 `dependency`가 아닌 것.
  선행 문항 때문에 남은 문항은 선행 문항을 따라간다.
- 2a 보충 블록을 `supplement_round`로 빼서 같은 함수·검증·프롬프트로 다시 부른다. 단계 이름:
  `v4-supplement-late`, `v4-supplement-normalize-late`, `v4-coverage-supplement-late`, `v4-map-check-late`,
  `v4-coverage-duplicate-late`(러너 `v3_kind`가 기존 프롬프트로 찾는다).
- `out_of_scope` 판정 문항은 2a처럼 은행에서 빼고 offGoalQuestions에 남긴다. 그 뒤 임상 정리가 최종 은행으로 돈다.
- 새 목표에 대한 문항 검토는 다시 하지 않는다. 새 목표의 범위 점검 행이 적은 관계로 B가 붙인다.

## D. 남으면 멈춤
- C 뒤에도 과제가 아닌 검수 `ok`·비중복·범위 안 문항이 하나라도 있으면 의학 검토 전에 멈춘다.
  readiness.json(`unplacedQuestions`, `coverageFallback`)을 먼저 쓰고, 메시지에 남은 문항 ID와 사유를 적는다.
- 앞 계획의 「미배치 20% 초과 멈춤」은 D로 대체한다.

## 근거 (운영판 28편, 2026-11-14 운영 DB 읽기 전용 대조 + `runs/_root-generation`)
| | 장내세균편 | 나머지 27편 |
|---|---|---|
| A 결함 방향 | 75/138 (54%) | 최대 3/97 (3.1%) |
| 지도에 못 붙은 문항 | 107 | 125 |
| 범위 점검이 component를 답으로 본 문항 | 47 | 51 |
| B로 실제 붙는 문항(저장 판정으로 재조립, 계약 검증 통과) | 43 | 12 |
| C로 가는 문항(임시 조립 기준, dependency 제외) | 64 | 111 |
- B 실측은 `replay_b.py`(scratchpad)로 운영판 28편의 기록된 판정을 /2 규칙으로 다시 조립한 값이다. 같은 판정을 /1 규칙으로
  조립하면 게시된 결과와 같다(검사 포함). 「답으로 본」 98개 중 B로 붙는 것이 55개인 것은 범위 점검이 관계를 적지 않았거나
  (25개) 그 관계가 지도 점검에서 지지되지 않았기 때문이다.
- C 결과와 D 멈춤 빈도는 모델 호출이 필요해 미리 셀 수 없다. 계획의 실측 단계에서 잰다.

## 바꾸지 않는 것
- 프롬프트(`content/prompts/learning-links/v4/*`), 검수 판정, 중복 합침, 기존 게시판, v2·v3 파이프라인.
