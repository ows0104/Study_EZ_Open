# 관리 탭 로딩 지연 제거

## 문제와 사용자 효과
2026-11-10 사용자 요청 원문: 「관리 탭을 여는데 너무너무 오래걸려. 문제를 진단하고 해결해줘.」

관리 화면(`web/src/admin/AdminPage.tsx`)은 `GET /api/admin/overview`가 올 때까지 「불러오는 중…」만 보인다.
운영 Cloud Run 로그(2026-11-01~11-10)에서 이 요청은 **10~12초, 응답 19.3MB**였다.

## 범위와 성공 기준
- overview 응답에서 화면이 쓰지 않는 은행 수정 이력(`bank.revision`)을 뺀다. 운영 데이터 기준 20.0MB → 0.89MB.
- 서버가 그 이력을 DB에서 꺼내지도 않는다. `quiz_bank.validation`(json)은 한 번만 훑는다.
- 「Quiz Bank 신고」 탭의 `GET /api/admin/bank-feedback`(운영 3초)이 은행의 `validation`·원문 응답을 읽지 않는다.

## 근거·미정 사항
측정(운영 DB 읽기 전용 트랜잭션, 노트북에서):
- `quiz_bank` 40행. `validation` 압축 25MB / 풀면 87MB, 최대 1행 20MB(약리학 261013_02).
  그중 `externalEvidenceReview` 10MB·`conflictClarityReview` 8.7MB — 검토 이력이다.
- overview 응답 20.0MB 중 `lectures[].bank.revision` 19.1MB, `coverage` 0.47MB, 나머지 0.4MB.
- 웹은 overview의 `bank` 중 `questionCount`·`reviewCounts`·`builtAt`·`usable`·`open`·`status`만 읽는다.
  overview를 부르는 곳은 관리 화면 하나다(러너·브리지·확장 없음).
- 남은 것(이번 범위 밖): `card-review` 2초(편·카드마다 쿼리), `bank-review` 3.8초·1.2MB.
