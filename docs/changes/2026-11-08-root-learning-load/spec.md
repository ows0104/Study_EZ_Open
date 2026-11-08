# Spec — 뿌리 학습 요청 지연

모든 변경은 **응답 내용을 바꾸지 않는다.** 같은 입력에 같은 JSON·같은 상태 코드를 낸다.
DB 쓰기·스키마·문항·학습 기록은 바뀌지 않는다.

## 1. 개인 수정은 한 번에 읽는다 (`server/app/root_learning/content.py` `availability`)

현재 과제마다 `bank_personal.apply()` → `db.get(BankPersonalEdit, …)`로 한 번씩 DB를 왕복한다
(261104_02는 98과제 → 98회). 세션 읽기·개요·`/api/root-learning` 목록이 모두 이 함수를 지난다.

- 그 사용자·강의의 `BankPersonalEdit`를 한 질의로 읽고 `bank_personal.apply_edit()`에 넘긴다.
  Quiz Bank 목록(`bank_api/catalog.py`)이 이미 쓰는 방식이다.
- 수용: 과제 수와 무관하게 `bank_personal_edit` SELECT가 1회. 개인 수정된 과제의 문제 문구
  (`개인 수정본과 연결 목표의 일치 미확인`)와 가용 집합은 이전과 같다.

## 2. 은행 지문은 행이 바뀔 때만 다시 계산한다

`availability`·`evidence.attach_evidence`가 요청마다 `document_hash(row.bank)`(은행 전체의 정렬 JSON + SHA-256)를 만든다.

- `content.bank_hash(row)`: 프로세스 안에 `(subject, run_id) → (build_id, updated_at, 지문)`을 둔다.
  `build_id`나 `updated_at`이 다르면 다시 계산한다. `updated_at`이 없으면 저장하지 않고 매번 계산한다.
- `quiz_bank.updated_at`은 ORM `onupdate`로 모든 갱신에서 바뀐다. 서버 코드에 이 표를 원시 SQL로 고치는 곳은 없다(검색 확인).
- 등록 검증(`validate_registration`)은 드물게 불리므로 지금처럼 매번 계산한다.
- 수용: 같은 행으로 두 번 부르면 두 번째는 `document_hash`를 부르지 않는다. 은행을 고쳐 커밋하면
  다음 호출은 새 지문으로 판정한다(연결 재검토 문구가 나온다).

## 3. 필요 없는 큰 칼럼을 싣지 않는다

- `availability`의 `QuizBank` 적재에서 `raw_response`·`validation`·`review`·`usage`를 지연 로딩(`defer`)한다.
  쓰이는 곳이 있으면 접근 시 읽히므로 동작은 같다.
- 판 목록(`GET /api/admin/root-learning/lectures/{subject}/{run_id}`, `versions`)은 `document` 전체 대신
  `revision`·`document->>'title'`·`reviewed`·`digest`만 고른다.
- 참고 PDF(`read_source`)의 생성 판 조회는 `result`·`web_response`를 지연 로딩한다(`source_records`는 `packet`·`web_dispatch`만 쓴다).
- 수용: 응답 필드·값 동일. 판 목록 질의에 `root_content.document` 전체 칼럼이 없다.

## 4. 참고 PDF는 보이는 부분만 받는다 (`web/src/bank/RootPdfSlides.tsx`)

서버는 이미 Range를 지원하고 CORS가 `Accept-Ranges`·`Content-Range`·`Content-Length`를 노출한다.
PDF.js 기본값(스트리밍·자동 전체 받기) 때문에 22MB를 한 응답으로 통째로 받는다.

- API 경유(`proxyPath`)일 때만 `disableStream: true`, `disableAutoFetch: true`, `rangeChunkSize: 524288`을 준다.
  범위 요청 하나가 인증·DB 조회를 거치므로 기본 64KB보다 크게 잡아 요청 수를 줄인다.
- 서명 URL(`url`) 경로와 렌더링·캐시·해제 동작은 그대로 둔다.
- 수용: 웹 타입·빌드 통과. 로컬 고정물 서버에서 참고 PDF가 206 범위 응답으로 그려지고 전체 200 응답이 끝까지 내려오지 않는다.

## 데이터 보존

읽기 경로만 바꾼다. 학습 사건·세션·은행·개인 수정·생성 기록에 쓰지 않는다.
