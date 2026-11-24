# 족보 풀이 Z 무제한·답 선택 취소 — 설계

## 요구사항과 수용 기준

- 웹 `JokboSolve`는 이번 판의 행동을 결과 목록(`results`)으로 가진다. Z는 맨 뒤 결과 하나를 한 단계 되돌린다.
  - 표시를 고른 결과: 표시를 `before`로 되돌리고 그 문제 답 화면으로(#175 동작).
  - 표시 전(답 화면) 결과: 결과를 목록에서 빼고 고르기 전 문제 화면으로. 고른 선지는 비운다. 서버 답 기록을 취소한다.
- 「다시 고르기 전 Z 금지」(`undone`)를 없앤다. 첫 문제의 고르기 전 화면이면 Z는 아무것도 하지 않는다.
- 회독 `onFinish`는 마운트당 한 번(그대로).

## 책임·입출력 계약·오류 상태

- `POST /api/jokbo/events/{event_id}/items/{item_id}/answer` 응답에 `before`를 더한다(추가 필드):
  `{band, markedAt, lastResult, answeredAt}` — 이 답을 기록하기 직전 값. 줄이 없었으면 모두 null.
- 새 `POST /api/jokbo/events/{event_id}/items/{item_id}/answer/undo`, 본문 `{result, before}`:
  - 내 줄이 없거나 `last_result`가 `result`와 다르면 409.
  - `result`에 맞는 횟수(wrong/correct)를 1 줄인다(0 아래로 가지 않음). `ungraded`는 횟수 없음.
  - band·marked_at·last_result·answered_at을 `before`로 돌린다. band·result는 기존 값만 받는다(422).
  - 그 결과 횟수 0·band 없음·answered_at 없음이면 줄을 지운다(처음 푼 문항 취소 = 기록 없음).
  - 응답은 되돌린 뒤 `mark_json` 모양.
- 웹은 같은 문항의 답 기록·표시 쓰기·답 취소를 한 줄로 순서대로 보낸다(앞 요청의 `before`를 받아야 취소한다).
  답 기록이 실패했으면 취소도 보내지 않는다. 취소 실패는 풀이를 막지 않는다.

## 호환성과 데이터 보존

- DB 표·칼럼 변경 없음. 다른 사람 줄은 건드리지 못한다(user_id 기본 키).
- 이용현황 `jokbo_answer`는 `answered_at`이 있는 줄을 센다. 취소한 답은 이전 시각으로 돌아가 이번 풀이로 세지 않는다.
- 오답노트 화면은 기존 `postAnswer`를 그대로 쓴다(응답에 필드가 하나 늘 뿐).
