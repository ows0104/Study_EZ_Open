# 모아풀기 강의별 중요도·저장값 기본 — 설계

## 요구사항과 수용 기준

- M1. `GET /api/root-learning/lectures/{subject}/{runId}/mix` 응답에 `focus`: 이 사용자가 그 강의에 저장한 중요도(TIERS 순서) 또는 `null`.
- M2. 시작 화면 강의 줄의 중요도 = 이 화면에서 바꾼 값 → 없으면 `mix.focus` → 없으면(null·빈 목록·옛 서버) 네 중요도 전부.
- M3. 중요도는 범위 슬라이더(`web/src/bank/TierRange.tsx`, 오늘 학습 `FocusRange`와 같은 부품)로 고른다. 강의별 슬라이더는 처음부터 펼친다
  (`aria-expanded=true`), 「강의별」 버튼으로 접을 수 있다. 저장하지 않으므로 움직일 때마다(live) 수가 바뀐다. 손잡이 이름 앞에 강의명·「전체」.
- M4. 전체 슬라이더: 모든 강의의 구간이 같으면 그 구간, 다르면 가장 넓게 덮는 구간과 「강의마다 다름」. 움직이면 모든 강의를 그 구간으로.
  선분 위 수는 강의 합.
- M4a. 저장값이 비연속이면 가장 낮은 것~가장 높은 것을 처음 값으로 쓴다(보이는 구간과 실제 거름이 같게).
- M5. 모아풀기 화면에서 바꾼 중요도는 `PUT …/focus`로 보내지 않는다.

## 책임·입출력 계약·오류 상태

- 서버: `content.saved_focus(db, subject, run_id, user_id)` — `_last_focus`가 없으면 None. `focus_for`(처음 값 포함)와 별개.
- 웹: `RootMixInfo.focus?: RootTierName[]|null`. 응답에 없으면 M2의 마지막 단계.
- 읽기만 추가. 기존 `/mix` 필드·`/mix-sessions` 요청 모양 그대로.

## 호환성과 데이터 보존

- 새 웹 + 옛 서버: `focus`가 없어 지금과 같은 처음 값(전부). 옛 웹 + 새 서버: 새 필드를 무시.
- DB 쓰기·표·학습 기록·복습 일정·오늘 학습 계획 변경 없음.
