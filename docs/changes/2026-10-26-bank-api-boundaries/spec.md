# 설계

- server/app/routes/bank.py는 기존 router/admin_router와 호출자 import의 호환 진입점으로 유지한다.
- bank_api/에 common, publication, editing, feedback, catalog, personal, state,
  presentation, study 책임을 둔다. 각 파일은 필요한 의존성만 명시적으로 import한다.
- 동작 함수·입력 모델·데코레이터 본문은 AST가 동일하게 이동한다. URL/메서드/요청·응답
  OpenAPI/상태 코드/인증 의존성은 변경하지 않는다. 공유 상태나 런타임 import 마술은 추가하지 않는다.
- 학습 선택·모아풀기·평가 후 다음 문항은 현재 서로 호출하므로 study에 유지한다.
  세부 분리는 서비스 인터페이스를 정의하는 이후 작업이다.
- 기존 외부 호출자 import는 유지하고 테스트 mock은 실제 정의/사용 모듈로 옮긴다.
- test_bank_coverage 실패는 원본과 이관 후 전체 JSON 비교가 메타데이터 추가를 허용하지
  않아 발생했다. 실제 역사적 평가·시간·등급·숙련도·원본 보관을 검증하도록 바꾼다.
  운영 bank_retention/study_retention 및 학습 알고리즘은 변경하지 않는다.
- 신규 문항에 과거 평가가 생기지 않으며 전후 은행과 원본 상태를 보관하는지 검사한다.

구현 상세: 동명 FeedbackIn 모델의 기존 OpenAPI component 이름을 유지하기 위해
그 클래스에 고정 __module__ 메타데이터를 둔다. 이 한 모델 메타데이터를 제외한
96개 함수·모델의 AST와 상수는 그대로이며 전체 OpenAPI 동등성으로 확인한다.
해당 모듈은 문자열 지연 annotation을 사용하지 않아 옛 진입점의 초기화 순서에 의존하지 않는다.

전체 검사에서 확인된 기존 실패도 같은 로컬 호환성 범위에서 해결한다.
- personal_priority: 빌드 ID만 변경한 동일 문항은 현행 migrate 규칙에 따라 개인 중요도를
  보존한다. 테스트는 이를 확인하고, 내용이 달라진 동일 ID에서는 승계하지 않는 반례를 추가한다.
- study_loading: excluded decisions 조회는 build_id/state와 ORM 식별 키만 필요하다.
  db.get의 load_only 옵션으로 이전 보관 상태를 불필요하게 읽지 않는다. 기존 세션의
  identity map·조회 결과·보존 동작은 유지한다. SQL 제외 검사와 API 회귀 검사로 확인한다.
