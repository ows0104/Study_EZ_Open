# v4 prompts — provenance

root-generation/4(요청명 map-tree/3)의 단계 프롬프트다. 각 파일은 v3의 같은 이름 파일을 복사한 뒤 docs/changes/2026-11-10-importance-at-authoring(spec R1–R7)이 요구한 곳만 바꿨다. 첫 줄의 단계 표시는 root-generation/4로 바꿨다.

| 파일 | v3와 다른 점 |
|---|---|
| coverage.md | 한 문항이 목표 전체를 답해야 covered이던 규칙을 component 합집합 규칙으로 바꿈(그림 목표는 visual_verdict ok인 그림 문항 하나 이상). 「부분 사실의 합집합으로 종합 판단을 대신하지 않는다」와 「units가 없는 종합 방향은 한 문항의 전체 회상이 필요」 삭제. `duplicates` 지시 추가 |
| add.md | 빈 목표는 빠진 component만 받음(`missing_component_ids`). 최상위 `question_importance`와 근거 판정 기준(kind 표) 추가. importanceTable 문단을 문항 근거 문단으로 바꿈 |
| fix.md | `question_importance` 추가(답 내용이 바뀔 때만 근거를 다시 판정). covered_goals를 「묻는 component 유지」로 바꿈. importanceTable 문단을 문항 근거 문단으로 바꿈 |
| map-check.md | 중요도 근거 입력·판정 지시 전부 삭제. target_checks는 목표 내용·범위만 판정 |
| item-review.md | 판정이 아닌 기록 `importance_note` 추가. 입력에 `evidence_source`가 있으면 정답 근거 필기 쪽 `evidence` 추가(docs/changes/2026-11-11-evidence-from-citations, review-evidence/1). 입력에 `map_relations`가 있으면 문항이 회상시키는 지도 관계 `relations` 추가(docs/changes/2026-11-11-place-by-review, review-relations/1) |
| point-supplement.md | 포인트는 `{point, source_refs}`만. 「중요도 근거」 절과 범례 문단 삭제 |

같은 변경으로 `../point-extract-v4.md`·`../point-output-v4.schema.json`(포인트 근거 삭제, `exam-point-extract/4`, notebook_profile 유지)과 `../map-tree/bank-task-v4.md`(question_importance)·`point-audit-v4.md`·`point-repair-v4.md`(중요도 근거 검수·보완 삭제)를 만들었다.
context.md·brief-fix.md·supplement-normalize.md는 바뀐 것이 없어 복사하지 않았다. v4 실행도 v3의 그 파일을 그대로 쓴다.

`normalize.md`는 `../automation/extract-v2.md`를 복사해 docs/changes/2026-11-11-v4-normalize-components(R1)가 요구한 곳만 바꿨다: component는 따로 채점할 내용 하나, 해석상 주의는 component 밖, 포인트 방향과 겹치는 지도 관계 방향·이름만 끼운 cue 틀 금지. 단계 이름이 `normalize`라서 러너가 입력의 `_pipeline_version`(root-generation/4)으로 이 파일을 고른다. /2·/3은 extract-v2.md 그대로다.

docs/changes/2026-11-12-goal-dedupe(피코르나 261111_02에서 같은 답의 문항 3개가 과제가 된 것)가 바꾼 곳:
- coverage.md: component에 섞인 해석상 주의는 판정에 넣지 않음(R1). 중복 묶음은 새 문항과 기존 문항을 함께, 부분만 답한 문항끼리도 비교(R4).
- add.md: `goals[].asked`(그 목표를 이미 묻는 문항과 빠진 부분의 판정)를 받아 같은 답을 다시 쓰지 않음. 쓸 문항이 없으면 빈 출력(R3).
- normalize.md: 「…하되, …은 아님을 구별한다」 꼴 포인트는 사실만 component에(R2).
