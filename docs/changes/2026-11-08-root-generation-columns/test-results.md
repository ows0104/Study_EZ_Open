# 검사 결과 — 관리자 generation GET의 큰 JSON 적재

모두 격리 SQLite(`server/local_test_data/roots-*`). `server/.env`·운영 DB는 쓰지 않았다.
명령: `server/`에서 `PYTHONPATH=<worktree 루트> <server/.venv>/python.exe -m tests [이름]`.

| 검사 | 수정 전 코드(cc67288b) | 수정 뒤 |
|---|---|---|
| `test_root_generation_columns` | **실패** — 첫 상황(웹 응답 대기)의 폴링이 `result`·`web_dispatch`·`web_response`를 모두 읽음 | 통과 |
| 같은 검사에서 칼럼 단언만 뺀 임시 사본(응답 동일성 9상황) | 통과 — 기준 사본이 수정 전 코드와 같다는 확인 | — (사본은 지움) |
| `test_root_generation_poll` | 통과 | 첫 폴링 단언을 고친 뒤 통과 |
| `-m tests root_` (21개) | — | 전부 통과 |
| `-m tests` 서버 전체 | — | **전부 통과 — 122개** |

확인하지 못한 것: 운영 지연. 격리 SQLite에서는 원래 지연(2.3s)이 재현되지 않는다.
배포 뒤 운영 로그에서 `261104_02` generation GET을 수정 전과 나란히 재기 전에는 줄었다고 적지 않는다.
