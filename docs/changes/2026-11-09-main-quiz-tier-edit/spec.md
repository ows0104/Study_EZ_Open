# Main-Quiz 풀이 중 내 중요도 변경 — 설계

## 요구사항과 수용 기준
- 사용자 지시(2026-11-09): 풀이 중 중요도를 바꿀 수 있게 하고, 학습 간격에는 Quiz Bank의 목표 기억률 방식을 쓴다.
  적용 범위는 「새 평가부터 적용」이다. 이전 평가의 예정일은 바꾸지 않는다.
- `PUT /api/root-learning/lectures/{subject}/{run_id}/questions/{question_id}/tier`
  본문 `{requestId, tier: "Essential"|"Core"|"Important"|"Optional"|null}`. null은 원래대로다.
  응답은 `{question, rescheduled}`. `question`은 학생 앞면에 `tier`·`originalTier`·`personalTier`·`targetMastery`를 싣는다.
  `rescheduled`는 이 문항에 목표 기억률로 잡힌 평가가 있어 예정일이 다시 계산됐는지를 나타낸다.
- 같은 requestId를 다시 보내면 같은 응답(멱등), 내용이 다르면 409. 판에 없는 문항은 404, 잘못된 tier는 422.
  원래 중요도와 같은 값을 고르면 원래대로(null)로 저장한다.
- 앞면 `tier`는 개인 값 → 판 문항의 tier(`Must-Know` 표기는 `Essential`) → `Core` 순으로 정한다.
  `targetMastery`는 아래 목표 기억률이다. 세션 GET·prepare·문제 수정·중요도 응답이 모두 같은 값을 쓴다.

## 책임·입출력 계약·오류 상태
- 새 자기평가 사건(`ratingPolicy: roots-four-rating/2`)에는 기존 `ratingParameters`와 함께
  Quiz Bank 숙련도 정책을 그대로 복사한 `targetParameters`(alpha·ratings·maxTarget·targets·tierTargets)를 저장한다.
  `targetParameters`가 없는 이전 사건은 지금까지처럼 `ceil(S)` 간격을 유지한다. 개인 중요도도 이전 사건에는 영향이 없다.
- 숙련도 M은 Quiz Bank `record_rating`과 같은 방식으로 계산한다. 각 방향의 모든 평가(이전 평가 포함)를 순서대로 반영한다.
  - 직전 평가 이후 경과 시간만큼 망각 곡선 1/(1+t/9S)로 감쇠시킨다.
  - Good·Easy는 감쇠 전 값, Again·Hard는 감쇠 후 값을 기준으로 삼는다.
  - 갱신식은 `(1−α)·기준 + α·점수`다.
  - 이전 3단계 사건은 missed→Again, partial→Hard, independent→Good으로 바꾸어 넣는다.
- 목표 기억률은 Quiz Bank `target_for`와 같다.
  - 개인 중요도이거나 Must-Know이면 tier 목표(.90/.85/.78/.55)를 쓴다.
  - 그 밖에는 판의 `retrieval_plan.target_mastery`를, 그것도 없으면 `importance` 단계 목표를 쓴다.
  - 어느 경우든 maxTarget과 tier 목표를 넘지 않는다.
- 간격은 `9·S·(M/목표−1)`일을 올림하고 최소 1일로 한다. Main-Quiz 정책의 `max_days`(30)와 시험 상한은 그대로 둔다.
  안정도 S는 기존 Main-Quiz 계산(Quiz Bank `next_stability`)을 바꾸지 않는다.
- 중요도 저장: `root_event(kind='tier', session_id='', revision=활성 판)`.
  payload는 `{question_id, tier, originalTier, tierPolicy:'roots-personal-tier/1', seq, _request}`다.
  - 판마다 문항별 마지막 사건이 유효하다. 정렬 순서는 시각 → `seq` → 요청 ID다.
  - 다른 판의 사건은 읽지 않는다.
  - 학습자의 현재 중요도가 그 문항의 목표 기억률 평가 전부의 목표가 된다. Quiz Bank가 불러올 때 다시 계산하는 것과 같다.
- 순서(`planning.plan`)·요약의 `important`·회상 판정 규칙은 바꾸지 않는다. 예정일이 바뀌어 생기는 차이만 있다.
- 이용현황: `usage_actions.ACTIONS`에 `root_tier`(`rootTiers`), `usage._root_field`에 `tier`를 추가한다.

## 호환성과 데이터 보존
- DB 스키마 변경은 없다. 기존 사건·학습 기록·개인 수정본은 바꾸지 않는다. 이전 평가의 예정일도 그대로다.
- 배포 뒤 첫 네 단계 평가부터 목표 기억률 간격이 적용된다. 중요한 문항은 숙련도가 목표에 닿을 때까지 다음 날 다시 나올 수 있다.
- Z(되돌리기)는 자기평가 취소만 한다. 중요도는 「원래대로」로 되돌린다.
- 웹은 서버 응답의 `question`으로 현재 문항을 바꾸고, 미리 받은 문항(frames)을 다시 받는다.
