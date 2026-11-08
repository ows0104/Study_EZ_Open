# 중요도 근거 통합 — 설계

## 1. 근거 (출제 포인트마다, `exam-point-extract/3`)
`points[].importance_basis`: `[{kind, refs:[{source_id,pages}], quote, reason}]`. 포인트에 근거가 없으면 빈 배열이다.

| kind | 뜻 | 점수 |
|---|---|---|
| `exam_forecast` | 교수의 출제 예고·「반드시」(완곡한 표현 포함) | 바로 Must-Know |
| `exam_exclusion` | 「시험에 안 낸다」 | Optional 고정(모든 것보다 앞섬) |
| `current_exam` | 올해 담당 교수의 족보 문항(연도마다 한 줄) | 연도당 2 |
| `learning_objective` | 학습목표·Summary·Take-home | 1.5 |
| `slide_emphasis` | 슬라이드 원본의 굵게·강조색·밑줄·네모(제목 제외) | 1 |
| `professor_remark` | 필기 주석에 옮긴 교수 발언(문장으로 출처 확인) | 1 |
| `writer_mark` | 필기자 하이라이트·밑줄(교수가 읽은 부분) | Important 바닥값, 필기강조형이면 +1 |
| `writer_stamp` | 필기자 중요 스탬프 | 0.5 |
| `writer_remark` | 출처가 불분명한 필기 첨언 | 0.5 |
| `clinical` | 임상적으로 중요 | 1 |
| `structural` | 다른 핵심 목표의 선행·상위 개념 | 1 |
| `other_exam` | 다른 교수의 같은 주제 기출 | 0.5 |
| `last_year_emphasis` | 작년 필기의 강조 | 0.5 |

같은 kind는 한 번만 센다. `current_exam`만 서로 다른 연도마다 센다.
강의 단위 `notebook_profile`: `{legend, emphasis_style: slide|verbal, reason}`.
`verbal`(필기강조형 교수)일 때만 `writer_mark`가 +1이다. 범례와 색은 단서로만 쓴다.

## 2. 계산 (`studyez_contracts/bank/importance.py`, 순수 함수)
- `score(basis, style)`의 판정 순서:
  1. exclusion이 있으면 Optional
  2. forecast가 있으면 Must-Know
  3. 나머지는 합계로 정한다: ≥4 Must-Know, ≥1.5 Core, ≥1 Important, 그 밖은 Optional
  4. `writer_mark`가 있으면 적어도 Important
- importance는 `{Must-Know(Essential):5, Core:4, Important:3, Optional:2}`(은행 3.3)다.
- 문항: 저작이 `point_ids`를 쓰고, 그 포인트들의 판정 중 가장 높은 것을 쓴다. 근거를 합치지 않고 포인트별 최대값을 쓴다.
- 개념: 그 개념 문항들의 최대값이다.
- 목표 3축: 그 목표에 속한 포인트(brief `points[].target_ids`)의 근거를 축별로 모은다.
  - exam ← forecast·current_exam·learning_objective·slide_emphasis·professor_remark·other_exam·last_year_emphasis·writer_*
  - clinical ← clinical
  - structural ← structural
  - 근거가 있으면 supported, 없으면 insufficient다. unreviewed는 생기지 않는다.

## 3. 파이프라인
- 포인트 추출·대조·보완 단계가 근거를 판정·검토한다(run.py의 대조 지시에 근거 확인을 추가).
- 원본 대조(source-v2): 입력 `importanceTable`(포인트별 근거·판정·목표별 3축)을 받아, `target_checks`로
  「목표의 근거가 원본과 맞는가」를 consistent/conflict/unknown으로 판정한다. 틀린 근거는 map_fix로 적는다.
- 저작(author-v2): 문항마다 `point_ids`를 쓰고, `tier`·`importance`는 표의 값을 옮긴다(조립 때 다시 계산되어 덮인다).
- 조립: `project_importance(bank, brief, table)`이 은행 3.3 snapshot을 만든다.
  - 문항·개념의 tier·importance와 `build_meta.schema_version`만 바뀐다.
  - 문서 review의 목표 3축도 표에서 투영한다.
  - 증명 `importanceProjection`을 manifest에 남기고, 계약이 같은 계산으로 다시 확인한다.
  - 원래 저작·검수 해시는 그대로다.
- 마지막의 중요도 보완 단계(`root_importance_review`)는 새 실행에서는 필요 없다. 옛 실행을 위해 남겨 둔다.

## 4. 측정·호환
- 경고(문항 유지):
  - 한 편의 Must-Know 비율이 운영 상위 10% 선(34%)을 넘을 때
  - 같은 예고 원문이 여러 포인트에 붙을 때. 선은 첫 실행의 분포를 보고 정하며, 그전까지는 보고만 한다.
- 은행 3.3: 3.2 형식에 문항 `point_ids`(선택)를 더하고 IMPORTANCE를 5/4/3/2로 둔다. 3.2 검증은 그대로다.
- Study Engine 정책표는 이미 importance 1–5를 모두 가진다. 엔진은 바꾸지 않는다.
- `quality_reasons`를 `validate_bank`와 같은 `without_retired` 은행으로 잰다. cloze `{정답}` 오탐을 없앤다.
