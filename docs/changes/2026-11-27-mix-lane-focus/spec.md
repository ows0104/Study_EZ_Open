# 모아풀기 강의별 중요도·저장값 기본 — 설계

## 요구사항과 수용 기준

- M1. `GET /api/root-learning/lectures/{subject}/{runId}/mix` 응답에 `focus`: 이 사용자가 그 강의에 저장한 중요도(TIERS 순서) 또는 `null`.
- M2. 시작 화면 강의 줄의 중요도 = 이 화면에서 바꾼 값 → 없으면 `mix.focus` → 없으면(null·빈 목록·옛 서버) 네 중요도 전부.
- M3. 강의별 칩은 처음부터 펼친다(`aria-expanded=true`). 「강의별」 버튼으로 접을 수 있다.
- M4. 전체 칩을 누르면 지금처럼 모든 강의에 그 중요도를 켜거나 끈다. 다른 중요도는 강의별 값(저장값 기본 포함) 그대로.
- M5. 모아풀기 화면에서 바꾼 중요도는 `PUT …/focus`로 보내지 않는다.

## 책임·입출력 계약·오류 상태

- 서버: `content.saved_focus(db, subject, run_id, user_id)` — `_last_focus`가 없으면 None. `focus_for`(처음 값 포함)와 별개.
- 웹: `RootMixInfo.focus?: RootTierName[]|null`. 응답에 없으면 M2의 마지막 단계.
- 읽기만 추가. 기존 `/mix` 필드·`/mix-sessions` 요청 모양 그대로.

## 호환성과 데이터 보존

- 새 웹 + 옛 서버: `focus`가 없어 지금과 같은 처음 값(전부). 옛 웹 + 새 서버: 새 필드를 무시.
- DB 쓰기·표·학습 기록·복습 일정·오늘 학습 계획 변경 없음.
