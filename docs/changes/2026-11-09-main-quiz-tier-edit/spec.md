# Main-Quiz 풀이 중 내 중요도 변경 — 설계

## 요구사항과 수용 기준
- `PUT /api/root-learning/lectures/{subject}/{run_id}/questions/{question_id}/tier`
  본문 `{requestId, tier: "Essential"|"Core"|"Important"|"Optional"|null}`. null = 원래대로.
  응답 `{question, rescheduled}`: `question`은 학생 앞면(`content.front`)과 같고 `tier`·`originalTier`·`personalTier`를 싣는다.
  `rescheduled`는 이 문항에 이미 평가된 방향이 있어 예정일이 다시 계산됐는지.
- 같은 requestId 재전송은 같은 응답(멱등), 다른 내용이면 409. 판에 없는 문항 404, 잘못된 tier 422.
  원래 중요도와 같은 값을 고르면 원래대로(null)로 저장한다.
- 앞면 `tier`는 개인 값 → 판 문항의 tier(`Must-Know` 표기는 `Essential`) → 없으면 `Core`.
  세션 GET·prepare·문제 수정 응답이 모두 같은 값을 쓴다.

## 책임·입출력 계약·오류 상태
- 저장: `root_event(kind='tier', session_id='', revision=활성 판)`, payload
  `{question_id, tier, originalTier, factor, tierPolicy:'roots-personal-tier/1', _request}`.
  판(revision)마다 문항별 마지막 사건이 유효하다. 다른 판의 사건은 읽지 않는다.
- 간격: Quiz Bank와 같은 망각 곡선 R(t)=1/(1+t/9S)과 Quiz Bank tier 목표(Essential .9·Core .85·Important .78·Optional .55)로
  t(tier)=9(1/R−1)을 구하고 `factor = t(내 중요도)/t(원래 중요도)`를 사건에 고정한다(정책이 바뀌어도 옛 사건 재현 불변).
  `state.replay`가 네 단계 자기평가 결과(`ratingDays`)가 있는 방향 중 마지막 평가 문항에 개인 중요도가 있으면
  `base = clamp(ceil(ratingDays × factor), 1, max_days)`, 시험 상한을 거쳐 마지막 평가일 기준 예정일을 다시 계산한다.
  안정도(`ratingDays`)는 바꾸지 않는다. 옛 등급(missed/partial/independent만) 사건은 그대로다.
- 순서(`planning.plan`)·요약의 `important`·회상 판정 규칙은 바꾸지 않는다. 예정일이 바뀌면 그 결과로만 달라진다.
- 이용현황: `usage_actions.ACTIONS`에 `root_tier`(`rootTiers`), `usage._root_field`에 `tier`.

## 호환성과 데이터 보존
- DB 스키마 변경 없음. 기존 사건·학습 기록·개인 수정본은 바꾸지 않는다. 개인 중요도를 지워도 사건은 남고 null 사건이 추가된다.
- Z(되돌리기)는 자기평가 취소만 한다. 중요도는 「원래대로」로 되돌린다.
- 웹은 서버 응답의 `question`으로 현재 문항을 바꾸고, 미리 받은 문항(frames)을 다시 받는다.
