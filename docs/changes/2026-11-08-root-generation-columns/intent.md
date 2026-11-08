# 관리자 generation GET의 큰 JSON 적재 — 의도

2026-11-08 사이트 로딩 진단 세션이 분리한 작업이다. 운영 Cloud Run(1 CPU·워커 1·concurrency 8)에서
한 요청이 오래 잡으면 같은 인스턴스의 다른 요청(학생 Main-Quiz 포함)이 밀린다.

## 근거

- `GET /api/admin/root-learning/lectures/{subject}/{run_id}/generation`(`latest()`)은 관리자
  화면이 응답 뒤 3초마다 다시 부른다(PR #21).
- 판이 쌓인 강의 `감염과 면역/261104_02`에서만 2–6초. PR #21의 `.limit(1)` 배포 뒤에도
  운영 한 표본 2.323초(수정 전 median 2.736초). 같은 구간 `/api/me` 0.961초라 몫은 가르지 못했다.
- 격리 SQLite에서는 2.5MB `result`도 0.045초. 남은 설명은 Supabase(transaction pooler)에서
  큰 JSON 칼럼을 끌어오는 전송·역직렬화다.

## 지금 한 번의 폴링이 끌어오는 것

1. `latest()`가 최신 판 **행 전체**를 읽는다: `packet`·`result`(2.5MB급)·`web_dispatch`
   (대체판은 `sourceSnapshots`를 싣는다)·`web_response`(웹 응답 원문 `raw`).
2. `public_job()`이 report를 만들려고 `row.result`를 통째로 쓴다. 출제가 끝난 판의 result는
   다시 바뀌지 않는데(`put_result`가 다른 digest를 거부) 폴링마다 다시 읽고 다시 계산한다.
3. `canonical_generation()`이 `supersededBy`를 따라가며 `db.get`으로 이전 판 행 전체를 읽는다.
4. `web_dispatch`·`web_response`는 응답에서 `dispatched`·`awaitingWeb`의 참/거짓으로만 쓰인다.

## 이번에 고치는 것

폴링 경로가 쓰지 않는 큰 JSON을 DB에서 가져오지 않는다. 응답은 한 글자도 바꾸지 않는다.

## 이번에 하지 않는 것

- 응답 필드를 빼거나 계약을 좁히지 않는다. 웹(`RootGenerationPanel.tsx`) 미변경.
- DB 스키마(새 칼럼·표)를 바꾸지 않는다 — report를 DB에 저장하려면 운영 DB 준비가 먼저라
  별도 승인이 필요하다. 이번에는 프로세스 안 캐시로 한다.
- `packet`은 응답(`input.conceptMap`·`points`·`scope`)과 중복 판정에 실제로 쓰므로 계속 읽는다.
- PR #24(`claude/root-learning-load`) 파일 `root_learning.py`·`content.py`·`evidence.py`·
  `RootPdfSlides.tsx`는 건드리지 않는다.
- 출제·은행·문항·학습 기록·검수 이력·운영 DB 미변경. 검사는 격리 SQLite만 쓴다(`server/.env` 미사용).
