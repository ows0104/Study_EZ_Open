# 관리 탭 로딩 지연 제거 — 설계

## 요구사항과 수용 기준
- `GET /api/admin/overview`의 `lectures[].bank`는 `summary(..., is_admin=True)`에서 `revision`만 뺀 값과 같다.
- overview의 은행 요약 쿼리는 `validation`에서 `pass·publication·coverage·errors·dropped`만 받는다.
  json 열을 키마다 `->`로 다시 파싱하지 않고 `json_each`로 한 번 훑어 `json_object_agg`로 모은다.
  `validation`이 객체가 아니면(JSON null) 빈 값으로 읽는다 — 오류가 아니다.
- `GET /api/admin/bank-feedback`은 `QuizBank`에서 `build_id·bank·review`만 읽는다. 응답은 그대로다.

## 책임·입출력 계약·오류 상태
- 강의별 관리자 요약(`GET /api/lectures/...`, `.../bank`)의 `revision`은 그대로 둔다
  (`tests/test_bank.py` 「생성 대화와 검수 상세가 관리자에게 연결된다」).
- 캐시(`app/admin_banks.py`)의 무효화 기준(updated_at·현재 필기 파일명)은 바꾸지 않는다.

## 호환성과 데이터 보존
- DB 스키마·데이터 변경 없음. 검토 이력·원문 응답은 DB에 그대로 있다. 읽는 열만 줄었다.
- 웹 타입 `BankSummary.revision`은 선택값이라 웹 변경이 필요 없다. 옛 웹·새 API, 새 웹·옛 API 모두 동작한다.
