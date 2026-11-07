# 구현 — 관리자 generation GET의 큰 JSON 적재

사용자 2026-11-08 「구현 승인」. 바꾼 파일은 `server/app/routes/root_generation.py` 하나와 검사 둘이다.

## root_generation.py

- `HEAVY`·`LIGHT`: `result`·`web_dispatch`·`web_response`를 `defer`한다.
- `present(column)`: `bool(dict | None)`과 같은 SQL 참/거짓(SQL NULL·JSON `null`·`{}` → 거짓).
- `heavy_flags(db, row)`: 이미 적재된 칼럼은 Python 값으로, 미뤄진 칼럼은 참/거짓만 질의.
  `request()`처럼 전체 행을 넘기는 호출은 질의가 늘지 않는다.
- `canonical_generation()`: `db.get(..., options=LIGHT)`. 판정 식은 그대로.
- `build_report(result)`: 기존 report 본문을 그대로 옮겼다(기존·대체판·큐레이션).
- `generation_report(row)`: `(id, result_digest)` 키 LRU 128, 잠금, 저장·반환 모두 복사본.
  digest가 없으면 캐시하지 않는다.
- `public_job(db, row, flags=None)`: 사슬로 판이 바뀌거나 flags가 없으면 `heavy_flags`.
  `report`·`awaitingWeb`·`dispatched`가 flags를 쓴다. 나머지 필드·순서 동일.
- `latest()`: `select(RootGeneration, *PRESENT).options(*LIGHT)…limit(1)` 한 번으로 행과 참/거짓을 받는다.

## 검사

- 새 `server/tests/test_root_generation_columns.py`: 아홉 상황에서 응답을 수정 전 `public_job` 사본과
  비교하고, 폴링 SELECT의 결과 칼럼(`cursor.description`)에 큰 칼럼이 언제 나오는지 단언한다.
- `server/tests/test_root_generation_poll.py`: 게시된 판의 첫 폴링 단언을 「LIMIT 한 번 + result 한 번」,
  두 번째 폴링을 「LIMIT 한 번」으로 고쳤다. 판 다섯·LIMIT·필드 보존 단언은 그대로.

## 남은 것

- 폴링마다 `packet`은 계속 읽는다(응답의 `input`과 중복 판정에 쓴다). 크기는 운영에서 재지 않았다.
- 캐시는 인스턴스 안에만 있다. 새 인스턴스의 첫 폴링은 result를 한 번 읽는다.
