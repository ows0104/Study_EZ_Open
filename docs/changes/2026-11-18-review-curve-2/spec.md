# Main-Quiz 복습 간격 2차 — 설계

## 요구사항과 수용 기준

새 평가 정책 `roots-four-rating/4`, 새 사건은 `curveParameters`(= `policy.CURVE`, `roots-curve/1`)를 얼린다.
`policy.curve_schedule(previous, updated, rating, when, target, tier, policy, exam_date, params)`가 복습일을 정한다.

R1 간격: `ceil(9·S·(1/target − 1))`, 최소 1일, 최대 policy max_days(30). target은 지금처럼 문항 중요도·「내 중요도」의 목표치.

R2 S(버티는 힘, `curveDays`):
- 처음: Again 0.25 · Hard 0.5 · Good 1 · Easy 2.
- Again: `min(1, max(0.25, S×1.2))` — 1일 이하로 묶고, 이미 약하면 본 만큼 조금 는다.
- Hard·Good·Easy: `S × (1 + (g−1) × L × (1.5 − D))`, g = Hard 1.35 · Good 2 · Easy 3, 최대 365.
- 같은 학습일의 두 번째 평가는 S·D를 바꾸지 않는다(Again은 예외).
- 예전 규칙으로 평가된 상태에서 넘어오면 그 `ratingDays`를 S로, D는 0.5에서 시작.

R3 늦게 맞힌 보너스: L = 실제 지난 날 ÷ 계획 간격(`baseDays`, 압축 전), 최대 2. 일찍 풀면 1보다 작아 덜 는다.

R4 난이도 D(0~1, `difficulty`): 처음 Again 0.8 · Hard 0.65 · Good 0.5 · Easy 0.3. 다음부터 Again +0.15, Hard 0, Easy −0.1,
Good은 0.5 쪽으로 20%.

R5 시험 압축: Essential·Core(`examTiers`)만 `exam_fraction` 상한을 받는다. 다른 등급은 `examPressure: false`를 저장하고
`effective_due`가 압축하지 않는다. 이 키가 없는 예전 상태는 지금처럼 압축.

R6 재생: `targetParameters`와 selfRating이 있는 모든 평가(/2·/3·/4)를 R1~R5로 읽는다. 사건의 `curveParameters`가 있으면 그것,
없으면 지금의 CURVE. targetParameters 없는 11-09 이전 평가와 세 단계 평가는 그대로.

수용 기준(매번 같은 평가, 복습일에 풀 때, 첫 45일):

| | Essential | Core | Important | Optional |
|---|---|---|---|---|
| Again만 | 매일 | 0~6 매일, 뒤 2일 간격 | 0,1,2,3,5,7,9,11,… | 0,2,5,8,12,16,21,27,34,42 |
| Hard만 | 0,1,2,3,5,7,9,12,16,21,27,34,43 | 0,1,3,5,7,10,13,17,22,29,38 | 0,2,4,7,10,14,19,26,34 | 0,4,9,16,25,36 |
| Good만 | 0,1,3,7,15,31 | 0,2,6,13,26 | 0,3,9,20,41 | 0,8,23 |
| Easy만 | 0,2,9,34 | 0,4,15 | 0,6,24 | 0,15 |

- Core: Again 뒤 Good 0,1,2,4,7,11,19,34 · Hard 뒤 Good 0,1,3,6,12,23,43 · Good 두 번째를 두 배 늦게 0,2,10,20,40.

## 책임·입출력 계약·오류 상태

- 학습률·카드 단계의 M은 그대로(`next_mastery`, /3). M의 망각에 쓰는 `ratingDays`는 min(30, S).
- 저장 응답·DB 형식 변경 없음. 새 사건 payload에 `curveParameters`가 더해진다.

## 호환성과 데이터 보존

- 사건은 고치지 않는다. 읽는 규칙만 바뀐다(R6). 병합 즉시 지난 평가의 복습일이 다시 계산된다.
- 오늘 목록 순서는 그대로(intent의 「범위에서 뺀 것」).
