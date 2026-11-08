# 검사 결과 — 뿌리 학습 요청 지연

기준: 브랜치 `claude/root-learning-load`, origin/master `cc67288b` 위. 모든 서버 검사는 `tests`의 격리 SQLite·로컬 저장소에서 돌았다.
운영 DB(`server/.env`)는 쓰지 않았다. 2026-11-08 실행.

| 검사 | 결과 |
|---|---|
| 새 서버 검사 `-m tests root_learning_load` | 통과 |
| 같은 검사를 수정 전 코드(origin/master 별도 worktree)에 | **실패** — 과제 3개에 `bank_personal_edit` SELECT 3회 (검사가 실제 결함을 잡는지 확인) |
| 서버 전체 `-m tests` | 통과 122/122 |
| 저장소 `pytest tests/development` | 51 통과, 2 건너뜀 |
| 웹 `npm run build` (`tsc -b` 포함) | 통과 |

서버 검사는 `PYTHONPATH=<worktree 루트>`로 이 worktree의 `studyez_contracts`를 썼다.
처음에 venv의 editable 설치(주 체크아웃 `a3f67d13`의 옛 계약)를 집어 root 검사 11개가 import·422로 실패했다.
코드 변경과 무관한 환경 문제이며 위 실행으로 대체했다.

## 새 서버 검사가 확인하는 것 (`server/tests/test_root_learning_load.py`)

1. `availability`: 과제 수와 무관하게 개인 수정 SELECT 1회. 개인 수정 과제의 차단 문구·가용 집합이 과제별 조회와 같고 다른 사용자의 수정은 섞이지 않는다. 은행 SELECT에 `raw_response`·`review`가 없다.
2. 은행 지문: 같은 행 두 번 → `document_hash` 1회. 은행 내용을 고쳐 커밋하면 다시 계산해 「연결 재검토」로 막고, 되돌리면 다시 열린다. `build_id`가 바뀌면 막는다.
3. 판 목록: 응답(판·제목·검토·지문·순서·활성 판)이 문서 전체를 읽은 값과 같고, 질의는 `document`를 통째로 고르지 않는다(제목만 JSON에서 추출).
4. `active_generation(light=True)`: 질의에 `result`·`web_response`가 없고, `packet`·`web_dispatch`는 그대로, `result`는 접근하면 읽힌다.

## PDF.js 범위 읽기 (임시 Node 하네스, 저장소에 넣지 않음)

pdfjs-dist 6.5.438(legacy, Node fetch), Range를 지원하는 로컬 서버, 15.9MB·58쪽 강의 PDF(`runs/250826_05/.../annotated.pdf`).
한 쪽의 `getOperatorList()`까지 마친 뒤 1.5초 더 기다려 내려간 바이트를 셌다.

| 옵션 | 쪽 | 내려간 바이트 | 요청 수 | 통째 요청 |
|---|---|---|---|---|
| 기본값(수정 전) | 1 | 16.48MB | 10 | 15.91MB 끝까지 |
| `disableStream`·`disableAutoFetch`·512KB | 1 | 1.88MB | 5 | 0.13MB에서 중단 |
| 기본값(수정 전) | 20 | 16.87MB | 13 | 15.91MB 끝까지 |
| `disableStream`·`disableAutoFetch`·512KB | 20 | 2.41MB | 6 | 0.13MB에서 중단 |

한계: 브라우저가 아니라 Node다. 브라우저의 fetch·캐시는 다를 수 있다. 로그인 상태의 실제 화면 렌더링은 확인하지 못했다(로컬 서버를 브라우저 창에서 열 수 없음). 운영 반영 뒤 Cloud Run 로그의 `sources/` 응답 크기로 확인한다.

## 남은 위험

- 범위 요청마다 인증·`active()`·생성 판 조회·R2 HEAD를 지난다. 512KB 청크로 쪽당 5–6회 수준이다.
- 처음의 통째 GET을 PDF.js가 중단하면, 서버의 R2 스트림은 명시적으로 닫히지 않고 GC 때 정리된다(기존에 사용자가 다운로드 중 이탈할 때와 같은 동작, 이번 범위 밖).
- 은행 지문 캐시는 `quiz_bank.updated_at`을 믿는다. 서버 코드에 이 표를 원시 SQL로 고치는 곳은 없지만, DB를 직접 고치면 `updated_at`도 함께 바꿔야 한다.
- `generation` GET(관리자)은 #21 뒤에도 2.3s(그 세션의 운영 측정). `public_job()`·`canonical_generation()`이 최신 판의 `result`를 통째로 읽는다. `root_generation.py`는 이번 범위에서 뺐으므로 후속 작업이다.
