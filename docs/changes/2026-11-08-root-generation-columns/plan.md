# 구현 계획 — 관리자 generation GET의 큰 JSON 적재

브랜치 `claude/root-generation-columns` (origin/master `cc67288b` 위).
대시보드 claim `a090df57`. 겹치는 행: 없음. `claude/root-learning-load`(PR #24)가 이 일을
후속 후보로 적어 두었고, 그 세션이 이 작업을 분리했다. #24 파일은 건드리지 않는다.

## 1. 큰 칼럼 지연과 참/거짓 식 (`root_generation.py`)

- `HEAVY = (defer(result), defer(web_dispatch), defer(web_response))`
- `present(col)`: `CASE WHEN col IS NULL THEN false WHEN CAST(col AS TEXT) IN ('null','{}') THEN false ELSE true END`
- `flags(db, row)`: 세 칼럼이 이미 적재돼 있으면 Python `bool`로, 아니면 그 행 id로
  `present(...)` 셋만 SELECT.

## 2. `latest()`

`select(RootGeneration, present(result), present(web_dispatch), present(web_response))
.options(*HEAVY).where(...).order_by(created_at.desc()).limit(1)` 한 번. 찾은 참/거짓을
`public_job(db, row, known=...)`에 넘긴다. 질의 수는 지금과 같은 하나(캐시에 없는 판이면 result 한 번 더).

## 3. `canonical_generation()`

`db.get(RootGeneration, id)` → `db.get(RootGeneration, id, options=HEAVY)`. 나머지 판정 동일.

## 4. `public_job()`

- `row = canonical_generation(db, row)`; 판이 바뀌었거나 `known`이 없으면 `flags(db, row)`.
- report: result가 있으면 `cached_report(row)` — 키 `(id, result_digest)`, digest 없으면 캐시하지 않음.
  계산 본문(기존 리포트·대체판 `replacement_report`)은 함수로 옮기기만 하고 바꾸지 않는다.
- `dispatched = has_dispatch`, `awaitingWeb`은 `not row.web_response` 자리에 `not has_response`.

## 5. 검사 (`server/tests`)

| 검사 | 확인하는 것 | 수정 전 코드 |
|---|---|---|
| 새 `test_root_generation_columns.py` | (a) 폴링 SELECT의 결과 칼럼(`cursor.description`)에 `result`·`web_dispatch`·`web_response` 없음, 같은 판 두 번째 폴링은 result를 안 읽음, 대체 사슬(`supersededBy`)도 같음 (b) 여러 상태(출제 중·게시·대체판 정책·웹 대기·`{}`/JSON null/SQL NULL·중복 사슬)의 응답이 **수정 전 `public_job` 사본**을 전체 행으로 돌린 값과 같음 (c) digest가 바뀌면 report 다시 계산 | (a) 실패, (b)(c) 통과 |
| 기존 `test_root_generation_poll.py` | SELECT 하나·LIMIT. 게시된 판의 **첫** 폴링은 result를 한 번 더 읽으므로 그 단언만 「첫 폴링 ≤2, 두 번째 1」로 고친다 | — |
| 기존 root 서버 검사 전부 | 중복·재개·웹 출제·대체판·병렬 동작 유지 | 통과 |
| 서버 전체 `-m tests` | 회귀 없음 | 통과 |

명령: worktree에서 `PYTHONPATH=<worktree 루트>`로
`../../server/.venv/Scripts/python.exe -m tests`(server/ 안에서). 격리 SQLite만 쓴다.

## 6. 배포와 확인

master 병합 = API 자동 배포. **사용자 승인 뒤에만** 병합한다.
배포 뒤 운영 로그에서 같은 엔드포인트(`261104_02` generation GET)의 지연을 수정 전(2.3s)과 나란히
`deployment.md`에 적는다. 개선이 확인되지 않으면 성공으로 적지 않는다.
