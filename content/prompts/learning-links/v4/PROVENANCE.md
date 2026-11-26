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

docs/changes/2026-11-23-normalize-grouping(레오·코로나·노로 261118_05에서 같은 지시문으로 CLI는 포인트마다 목표 하나, Work는 강의 뼈대로 묶은 것)이 바꾼 곳:
- normalize.md: 「목표의 뼈대」 문단 추가 — 포인트와 목표는 1:1이 아님, 큰 축 root·갈래 branch·세부 leaf, 원본이 말하는 관계 kind, 답 조각마다 개념 금지, 포인트 순서로 찍어내기 금지(R1). 지도 관계 방향 중복 금지 문장을 「다른 목표(묶은 root·branch 포함)가 회상시키면」으로 넓힘(R2).

docs/changes/2026-11-23-fix-same-question(고치기가 같은 question_id로 다른 물음을 쓴 것, 레오 Q038·신종 Q075)이 바꾼 곳:
- fix.md: 고친 문항은 원래 문항이 묻던 것을 묻는다. 같은 물음 안의 셋(정답 교체·같은 범주 목록의 빠진 원소·줄이거나 나누기)을 적고, 다른 물음을 요구하는 지적은 이 ID에 적용하지 않고 이유를 exam_rationale에(R1).
- item-review.md: fix는 그 문항이 묻는 것 안에서 고칠 방향. 다른 물음은 note의 「별도 문항: …」, 그 이유만으로 design을 낮추지 않음(R2).

docs/changes/2026-11-26-answer-holds-the-link(피부근염 261124_02에서 줄기를 발문에 주고 끝의 이름만 물은 것, 사용자 「가장 중요한 부분을 답으로써 물어보지 않고」)이 바꾼 곳:
- presuppose.md: 발문이 사실로 준 판단·다음 할 일도 상위 연결로 적는다. 증례의 자료와 그 자료에서 나오는 결론을 가른다. 판단 연결의 point 꼴(R1).
- normalize.md: 존재 목표 문단에 판단·할 일 연결(R1).
- add.md·fix.md: 판단 연결의 존재 문항은 상황만 주고 판단을 답하게 함(R1, add). 싣지 않는 것 다섯 → 여덟(범주가 곧 판단인 말·핵심인 개수·판단과 중간 단계)과 한 가지 판단 기준(R4). 뜻풀이만 주고 이름을 답하게 하지 않음(R5, fix는 뒤집지 않음). `current_exam`은 족보 정답 선지가 말한 판단과 같은 층일 때만(R2).
- item-review.md: 같은 여덟 가지와 판단 기준(R4), 뜻풀이→이름 doubt(R5), 입력에 `exam_level`이 있으면 층이 어긋난 족보 연도 `off_level_exam_years`(R2, answer-level/1).
- `../map-tree/bank-task-v4.md`: `current_exam` 같은 문장(R2). `../../bank/bankPrompt.md` 1.85에 같은 원칙.
- supplement-normalize.md(새로 복사, 2026-11-26 재현 뒤): `../v3/supplement-normalize.md`에 component 하나 = 채점할 내용 하나, 입력에 `origin_questions`가 있으면 목표를 그 문항이 답하는 방향으로 쓰라는 두 줄을 더했다. item-review.md에 「오답 선지를 바로잡는 답은 같은 층」 예.
- map-check.md(2026-11-26 재현 2회 뒤): 관계 판정은 그 관계가 말하는 사실로 하고, 끝점 모양만 어긋나면 supported + map_fix(사실이 틀리면 conflict). presuppose.md: recalled_by는 그 연결 자체를 답하는 문항만, 판단·할 일 문항은 그 판단이 필요해지는 앞 연결 위에 선다.
