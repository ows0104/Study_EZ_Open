# v4 prompts — provenance

root-generation/4(요청명 map-tree/3)의 단계 프롬프트다. 각 파일은 v3의 같은 이름 파일을 복사한 뒤 docs/changes/2026-11-10-importance-at-authoring(spec R1–R7)이 요구한 곳만 바꿨다. 첫 줄의 단계 표시는 root-generation/4로 바꿨다.

| 파일 | v3와 다른 점 |
|---|---|
| coverage.md | 한 문항이 목표 전체를 답해야 covered이던 규칙을 component 합집합 규칙으로 바꿈(그림 목표는 visual_verdict ok인 그림 문항 하나 이상). 「부분 사실의 합집합으로 종합 판단을 대신하지 않는다」와 「units가 없는 종합 방향은 한 문항의 전체 회상이 필요」 삭제. `duplicates` 지시 추가 |
| add.md | 빈 목표는 빠진 component만 받음(`missing_component_ids`). 최상위 `question_importance`와 근거 판정 기준(kind 표) 추가. importanceTable 문단을 문항 근거 문단으로 바꿈 |
| fix.md | `question_importance` 추가(답 내용이 바뀔 때만 근거를 다시 판정). covered_goals를 「묻는 component 유지」로 바꿈. importanceTable 문단을 문항 근거 문단으로 바꿈 |
| map-check.md | 중요도 근거 입력·판정 지시 전부 삭제. target_checks는 목표 내용·범위만 판정 |
| item-review.md | 판정이 아닌 기록 `importance_note` 추가 |
| point-supplement.md | 포인트는 `{point, source_refs}`만. 「중요도 근거」 절과 범례 문단 삭제 |

같은 변경으로 `../point-extract-v4.md`·`../point-output-v4.schema.json`(포인트 근거 삭제, `exam-point-extract/4`, notebook_profile 유지)과 `../map-tree/bank-task-v4.md`(question_importance)·`point-audit-v4.md`·`point-repair-v4.md`(중요도 근거 검수·보완 삭제)를 만들었다.
context.md·brief-fix.md·supplement-normalize.md는 바뀐 것이 없어 복사하지 않았다. v4 실행도 v3의 그 파일을 그대로 쓴다.
