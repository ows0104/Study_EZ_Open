# 족보 1회 풀이를 회독에 기록 — 설계

## 요구사항과 수용 기준
- 새 표 `jokbo_round`(id varchar(32) PK, user_id varchar(64), event_id varchar(64), created_at timestamptz,
  인덱스 `(user_id, event_id)`, RLS 켬). 한 줄 = 족보 1회독. 시간표 칸(event_id)에 붙는다 — 족보 문서가 칸에 붙고,
  필기(Lecture)가 없는 칸에도 족보가 있다. `jokbo_mark`처럼 시간표 칸 외래 키는 두지 않는다(시간표 재적재에 기록이 지워지지 않게).
- `POST /api/jokbo/events/{eventId}/rounds` → `{"jokboRounds": n}`. 본인 것만. 볼 수 없는 족보(없음·관리자 전용)는 404.
  칸마다 30번까지(넘으면 409, 강의록 회독 상한과 같음).
- `GET /api/timetable` 각 칸에 `jokboRounds`(본인 수). `include_study=false`일 때는 0.
- 웹 `JokboPage`: 진입 화면에서 시작한 범위(또는 끝 화면 「다시 풀기」로 같은 범위)를 푼 판만 끝 화면에 닿을 때 한 번 POST.
  「이 문제만 다시 풀기」는 부르지 않는다. 기록 실패는 끝 화면을 막지 않는다.
- 회독 줄: 예습 → 강의록 → 족보 순. 칸에는 강의록+족보 합쳐 8토막까지, 패널은 각각 12토막까지(넘으면 합계 숫자).
  족보 토막(`rl-jokbo`)은 `color-mix(--ink-2 70%, --surface)` — 강의록(`--ink-3 70%`)보다 살짝 진하다. 누를 수 없다.
- 칸 툴팁·화면 낭독 설명에 「족보 n회독」. 안내 페이지 회독 설명에 족보 토막 한 줄.

## 책임·입출력 계약·오류 상태
- 서버: `routes/jokbo.py` `jokbo_round_counts`·`add_jokbo_round`, `routes/timetable.py`가 칸별 수를 싣는다.
- 웹: `JokboPage`(기록), `entries.ts`(칸에 `jokboRounds`), `ChipLearning`·`EventChip`(칸), `EventPanel`·`ReadEditor`(패널).
- 캘린더로 돌아오면 학습 집계 요청이 다시 나가 새 수가 보인다(기존 흐름 그대로).

## 호환성과 데이터 보존
- 기존 표·학습 기록·족보 문서·오답노트 표시는 바뀌지 않는다. 새 표에 행을 더하기만 한다.
- 웹은 `jokboRounds`가 없으면 0으로 본다 — 옛 API와 함께여도 깨지지 않는다.
- 새 API는 `jokbo_round` 표가 없으면 시간표 응답이 실패한다. **표를 먼저 만들고 병합(=API 배포)한다.**
