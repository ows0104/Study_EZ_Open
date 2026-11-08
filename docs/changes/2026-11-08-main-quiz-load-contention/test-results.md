# 검사 결과 — 2026-11-08

서버 검사는 저장소 루트를 `PYTHONPATH`에 두고 돌렸다. 이 worktree에는 `.venv`가 없어
`server/.venv`(주 체크아웃의 것)를 쓰는데, 거기 설치된 `studyez_contracts`가 주 체크아웃의
낡은 사본을 가리켜 `studyez_contracts.roots.parallel`을 못 찾았다(root 검사 11개 실패).
경로를 바로잡은 뒤 전부 통과했다. 코드 문제가 아니라 환경 문제다.

| 검사 | 명령 | 결과 |
|---|---|---|
| 새 서버 검사 | `python -m tests root_generation_poll` | 통과 1/1 |
| 같은 검사, 수정 되돌린 상태 | 같음 | **실패** — `LIMIT` 없는 SELECT가 `packet`·`result`·`web_dispatch`·`web_response`까지 14열을 끌어오는 것을 그대로 찍었다 |
| root 서버 검사 전체 | `python -m tests root` | 통과 20/20 |
| 서버 검사 전체 | `python -m tests` | 통과 121/121 |
| 저장소 전체 회귀 | `python -m pytest tests -q --ignore=…desktop_window --ignore=…status_window` | 2068 통과 · 1 실패 · 3 skip |
| 배포 스크립트·포장 | `python -m pytest tests/development/test_server_deploy.py tests/contracts/test_packaging.py -q` | 통과 |
| 배포 경화 | `python -m pytest tests/development/test_hardening.py -q` | 통과 19 · skip 2 |
| 웹 타입·빌드 | `npm run build` (`tsc -b` 포함) | 통과, 2.27s |
| 새 웹 단위 검사 | `node --test tests/root-generation-poll.test.cjs tests/adminPolling.test.cjs` | 통과 7/7 |
| 새 브라우저 고정물 | `web/tests/root-generation-poll.html`을 실제 Chrome에서 | 5개 PASS · `ALL PASSED` |

## 실패·환경으로 설명되는 것

- `tests/runner/test_desktop_control.py::test_shortcut_installer_supports_korean_filename_in_windows_powershell`
  1개 실패. 원인은 `scripts/install-runner-desktop.ps1:6`이 읽는 `.venv/pyvenv.cfg`가
  **이 worktree에 없다**는 것이다(`PathNotFound`). CI는 `.venv`를 만들고 그 파일을 먼저 찍는다.
  이 변경과 무관하며 수정하지 않았다.
- `test_hardening.py`는 처음 9개가 실패했다. 긴 scratchpad 경로 + pytest 임시 폴더가
  Windows 경로 한도를 넘었다(`FileNotFoundError [WinError 3]`). 짧은 `TEMP`로 다시 돌려 통과했다.

## 돌리지 못한 것

- `web/tests/bank-interactions.test.cjs`의 playwright 경로. 이 환경에 playwright가 없고
  `web/node_modules`에도 없다. 새 고정물 `root-generation-poll`을 그 목록에 등록해 두었고,
  확인은 같은 HTML을 vite(`web`, 127.0.0.1:5201)로 내고 실제 Chrome에서 읽어 대신했다.
  playwright가 있는 자리에서 그 목록째로 다시 돌릴 수 있다.
- 운영 Postgres에서 `.limit(1)`이 줄이는 실제 시간. 격리 SQLite는 결과 집합을
  스트리밍하므로 6판 × 276 KB에서도 0.0117초이고 운영 경로를 재현하지 못한다.
  **배포 후 운영 로그로 확인하고 `deployment.md`에 수정 전/후를 나란히 적는다.**
- 운영 화면에서의 확인. 관리자 Main-Quiz 화면의 실제 진행 중 작업으로는 확인하지 않았다.
  확인한 것은 같은 컴포넌트를 가짜 API로 띄운 실제 브라우저 렌더링이다.
