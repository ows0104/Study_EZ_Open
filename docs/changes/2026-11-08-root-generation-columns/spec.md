# 관리자 generation GET의 큰 JSON 적재 — 명세

대상: `server/app/routes/root_generation.py`의 `latest()`·`public_job()`·`canonical_generation()`.
`public_job()`을 같이 쓰는 `request()`(POST, 재사용 응답 포함)도 같은 결과를 낸다.

## 불변: 응답 동일성

`public_job()`이 돌려주는 dict는 수정 전과 **같은 값**이어야 한다. 특히:

| 필드 | 수정 전 계산 | 수정 후 계산 |
|---|---|---|
| `report` | `row.result`가 참이면 매번 result 전체로 계산 | 같은 함수로 계산하되 `(row.id, result_digest)`마다 한 번만. 결과는 복사해 돌려준다 |
| `dispatched` | `bool(row.web_dispatch)` | SQL에서 같은 참/거짓을 계산 |
| `awaitingWeb` | `… and not row.web_response and …` | 같은 식, `web_response`의 참/거짓만 SQL에서 |
| 나머지 | `packet`·`job`·작은 칼럼 | 그대로 |

「참/거짓」은 Python의 `bool(dict | None)`와 같아야 한다. 저장 값은 SQL NULL, JSON `null`
(ORM이 명시적 `None`을 이렇게 쓴다), `{}`(`reviewed_import`가 쓸 수 있다), 비어 있지 않은 dict
넷이다. SQL 식은 `NULL`·`'null'`·`'{}'`를 거짓, 나머지를 참으로 본다
(SQLite·PostgreSQL `json` 모두 `CAST(x AS TEXT)`가 저장 문자열을 돌려준다. SQLAlchemy 2.0.45에서 확인).

## 질의 칼럼

폴링 한 번(`latest()`)이 내보내는 `root_generation` SELECT의 **결과 칼럼**에
`result`·`web_dispatch`·`web_response`가 없어야 한다. 이 셋은 `defer`로 미루고, 필요한 참/거짓만
같은 SELECT의 계산 칼럼으로 받는다. `canonical_generation()`의 `db.get`도 같은 `defer`를 준다
(`Session.get(..., options=...)` — 이미 세션에 있는 행이면 질의하지 않는 동작은 그대로).

예외는 하나다: report 캐시에 없는 판을 처음 볼 때 `result`를 한 번 읽는다
(인스턴스마다, 판이 바뀔 때마다 한 번). 그 뒤 같은 판의 폴링은 result를 읽지 않는다.

## report 캐시

- 키: `(generation id, result_digest)`. 출제가 끝난 판의 result는 `put_result`·대체판 등록이 다른
  digest를 거부하므로 키가 같으면 값도 같다. digest가 없는데 result가 있는 행(현재 코드로는
  생기지 않음)은 캐시하지 않고 매번 수정 전처럼 계산한다.
- 크기: 최근 128판(LRU). 스레드 풀에서 부르므로 잠금을 둔다.
- 다시 시작한 인스턴스는 빈 캐시로 시작한다(첫 폴링에 한 번 읽는다). 다른 인스턴스와 공유하지 않는다.
  DB에 report 칼럼을 두는 길은 스키마 변경이라 이번 범위 밖(intent 참고).

## 실패 조건

- 지연된 칼럼은 접근하면 SQLAlchemy가 그때 읽는다. 다른 경로(`retain_duplicate`·`get_input`·
  `web_input` 등)가 `canonical_generation()`이 돌려준 행의 `result`를 읽어도 값은 같다 — 질의가 하나 늘 뿐이다.
- 운영 측정은 배포 뒤에만 가능하다. 격리 SQLite에서는 원래 지연이 재현되지 않으므로, 이 변경의
  효과는 「폴링이 큰 JSON을 끌어오지 않는다」까지만 검사로 확인하고, 운영 지연은 배포 뒤 로그로 따로 적는다.
  확인 전에는 지연이 줄었다고 쓰지 않는다.
