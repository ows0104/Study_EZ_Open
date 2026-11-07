# Implementation Plan — 뿌리 학습 요청 지연

브랜치 `claude/root-learning-load` (origin/master `cc67288b` 위), worktree `../Study_EZ_root-learning-load`.
대시보드 claim `b8049fe0`. 같은 화면의 `claude/main-quiz-load-contention`(PR #21)과는 파일을 나눴다(사용자 확인).

## 변경 파일과 순서

1. `server/app/root_learning/content.py`
   - `bank_hash(row)` 추가(프로세스 내 캐시, 키 `(subject, run_id)`, 값 `(build_id, updated_at, 지문)`).
   - `availability()`: `QuizBank`를 `defer(raw_response, validation, review, usage)`로 읽고, 지문은 `bank_hash`,
     개인 수정은 한 질의로 읽어 `bank_personal.apply_edit()`.
2. `server/app/root_learning/evidence.py` — `attach_evidence`의 지문 비교를 `content.bank_hash`로.
3. `server/app/routes/root_learning.py`
   - `versions()`: 칼럼 선택 질의(`revision`, `document['title'].as_string()`, `reviewed`, `digest`).
   - `active_generation(db, doc, *, light=False)`: `light`면 `result`·`web_response` 지연 로딩. `read_source`만 `light=True`.
4. `web/src/bank/RootPdfSlides.tsx` — `proxyPath`일 때 `disableStream`·`disableAutoFetch`·`rangeChunkSize: 524288`.
5. `server/tests/test_root_learning_load.py`(새 파일) — 아래 서버 검사.
6. `docs/changes/2026-11-08-root-learning-load/test-results.md` — 실제 검사 결과.

## 검사

| 검사 | 명령 (`server/`에서, 격리 DB) | 확인하는 것 |
|---|---|---|
| 새 서버 검사 | `.venv/Scripts/python.exe -m tests root_learning_load` | 개인 수정 SELECT 1회·결과 동일, 지문 캐시 재사용과 은행 변경 시 무효화, 판 목록이 `document`를 통째로 싣지 않음·응답 동일, `read_source`가 `result`를 싣지 않음 |
| 기존 뿌리 검사 | `.venv/Scripts/python.exe -m tests root` | 세션·개요·공개·생성·보존 동작 유지 |
| 은행·경로 | `-m tests bank`, `-m tests route_contract` | 개인 수정·경로 계약 유지 |
| 서버 전체 | `.venv/Scripts/python.exe -m tests` | 회귀 없음 |
| 웹 | `web/`에서 `npm run build` | 타입·빌드 |
| PDF.js 범위 | 임시 Node 하네스(스크래치): 20MB 합성 PDF를 Range 지원 로컬 서버로 내고 1쪽을 그릴 때 내려간 바이트를 수정 전/후 옵션으로 비교 | 통째 다운로드가 사라지는지. 브라우저와 다를 수 있으므로 한계를 함께 적는다 |

모든 서버 검사는 `tests`의 격리 로컬 DB에서 돈다. 운영 DB(`server/.env`)는 쓰지 않는다.

## 복원

코드만 바뀐다. 문제가 생기면 이 PR을 되돌리는 커밋 하나로 원상복구된다. DB·데이터 정리는 없다.

## 배포와 확인 (별도 승인)

master 병합 = 자동 배포(API → Pages). 병합은 사용자 승인 뒤에만 한다.
배포 뒤 운영 Cloud Run 로그에서 위 네 엔드포인트의 지연을 **수정 전/후로 나란히** `deployment.md`에 적는다.
#21 배포 효과와 섞이므로 #21만 반영된 구간(`cc67288b`)과 이 변경 반영 구간을 나눠 본다.
개선이 확인되지 않으면 성공으로 적지 않는다.

## 승인

2026-11-08 사용자 「Approve, build it」 — 이 계획의 변경 파일 1–6과 로컬 검사 범위의 구현 승인.
master 병합(=운영 자동 배포)은 포함하지 않는다.
