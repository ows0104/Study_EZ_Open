# Main-Quiz 복습 간격: 쉬운 문항이 곡선대로 빠지게 — 설계

## 요구사항과 수용 기준

R1. 새 평가 정책 `roots-four-rating/3`. 평가 사건의 `targetParameters`에 두 값을 더해 얼린다.
- `firstFromRating: true` — 숙련도가 없는(처음 평가하는) 과제는 M = 그 평가 값(Again 0·Hard 0.45·Good 0.95·Easy 1.0).
- `ratingAlpha: {Good: 0.5, Easy: 0.7}` — 맞힌 평가의 지수 평균 가중치. Again·Hard는 기존 `alpha` 0.35.
- 망각 곡선·목표치·안정도(S)·최대 30일은 그대로. 복습일 = M/(1+t/9S)가 목표치에 닿는 날(최소 1일).

수용 기준(매번 같은 평가, 복습일에 풀 때 첫 30일 안 출제일):

| | 지금 Easy | 바뀐 뒤 Easy | 지금 Good | 바뀐 뒤 Good |
|---|---|---|---|---|
| Essential | 0,1,2,3,4,5,8,18 | 0,3,10,29 | 0,1,…,7,9,… (12회) | 0,1,3,6,10,16,25 |
| Core | 0,1,2,3,4,8,23 | 0,4,14 | 0,1,2,3,4,5,7,12,22 | 0,2,5,10,19 |
| Important | 0,1,2,3,7,27 | 0,6,22 | 0,1,2,3,4,8,19 | 0,2,6,14 |
| Optional | 0,1,3,26 | 0,15 | 0,1,2,9 | 0,7,21 |

- 틀렸다가 맞히는 문항(Core, Again 뒤 Good 연속): 지금 1일 간격 6번 → 바뀐 뒤 4번(0,1,2,3,4,6,10). 어려운 문항은 남는다.

R2. `transition`은 selfRating이 있으면 도움 여부로 등급을 낮추지 않는다(Good·Easy → independent).
selfRating이 없는 예전 세 단계 사건은 지금처럼 `independent`+도움 → `partial`. 서버의 예전 클라이언트 거절(422)도 그대로.

R3. 지난 평가도 새 곡선으로 다시 읽는다(사용자 2026-11-18 「지금 시험이 곧인데 지난평가에도 이에 맞춰 복습일을 조정해줄래?」).
`ratingPolicy`가 `roots-four-rating/2`인 사건은 저장된 `targetParameters`에 R1 두 값을 더해 재생한다(`policy.replay_parameters`).
- 그 문항의 숙련도·다음 복습일·학습률이 처음 평가부터 /3 규칙으로 다시 계산된다. 오늘 복습 수가 바로 줄어든다.
- `targetParameters`가 없는 11-09 이전 평가는 그대로(목표치 간격이 없던 평가).

## 책임·입출력 계약·오류 상태

- `policy.target_parameters()`가 Quiz Bank 값에 R1 두 값을 더해 돌려준다. Quiz Bank(`study_engine`) 정책 파일은 고치지 않는다.
- `policy.next_mastery()`가 두 값을 읽는다. `state._rate`는 `policy.replay_parameters(payload)`로 파라미터를 받는다(/2는 R1 두 값 추가).
- 평가 저장 응답·DB 형식 변경 없음. 사건 payload에 `ratingPolicy`가 `/3`, `targetParameters`에 두 키가 더해진다.

## 호환성과 데이터 보존

- 사건은 고치지 않는다. 읽는 규칙만 바뀐다(R2·R3). 지난 /2 사건의 저장된 파라미터도 그대로 남는다.
- R3로 이미 평가한 문항의 다음 복습일이 바로 뒤로 밀리고, 보이는 학습률이 오른다.
- R2는 재생 규칙이라 지난 네 단계 평가에도 적용된다: 선지·지도·답만 보기 뒤 Good/Easy가 이제 independent로 읽혀
  인출·저장 칸, 「회상 가능」, goodDays가 오른다. R2만으로는 복습일과 학습률(M은 원래 selfRating을 썼다)이 바뀌지 않는다.
- 보이는 학습률은 M을 쓰므로 더 빨리 오른다(같은 곡선이라는 사용자 그림과 맞음).
