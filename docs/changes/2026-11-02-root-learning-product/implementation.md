# 뿌리 학습 제품 구현

- 공용 계약: studyez_contracts/roots. learning_links 검토·목표·방향을 재사용하고 은행 스냅샷, 채택 목표, 단일 방향 과제, 검토된 명시적 선행 연결, 동일성 연결을 검증한다.
- 별도 표: root_content/control/session/event. app.models 등록으로 app.cli init-db가 생성하고 PostgreSQL RLS hook을 실행한다. 기존 은행/학습/개인 수정은 읽기만 한다.
- 서버: app/root_learning/{content,state,policy,planning}.py, app/routes/root_learning.py. 사건 재생 집계, 도움/답만 보기/평가/취소 분리, 날짜별 고정 추천, 원래 문항/개인 제외 재검사, 판별 독립 기록을 제공한다.
- 웹: /bank/:subject/:runId/roots. RootLearning/RootSolve/RootMap/RootToday 및 useRootStudyWrites. 실제 Main-Quiz 진입과 학습 현황에서 준비된 범위를 연결한다. 독립 요청/초안 보관, 같은 ID 재전달, 최신 GET 동기화와 충돌 응답 보존을 적용한다.
- 운영자 기능: 새 roots/1 JSON을 비공개 등록 후 검토 확인과 대상 계정을 선택하여 활성화한다. 이 UI는 기존 은행을 수정하지 않는다. 공개/중지 사건을 별도 보존한다.
- 범위: 지도에서 같은 목표가 여러 곳에 연결되어도 분모는 고유 목표 합집합이다. 미준비/미확정 필수 방향은 남기고 회상 완료를 막는다. 중요한 미학습 표시는 시험 또는 임상 중요성 근거가 supported인 목표이며 구조적 선행 필요는 별도의 명시적 선행 연결로 처리한다. 자동 합산 중요도 점수는 만들지 않는다.
- 시간/정책: 세션에 전체 정책과 자료 판·학습일·유한 목록을 저장한다. 당일 오답은 목록을 늘리지 않는다. 평가에 따른 회상 변화와 기한 경과 변화는 따로 표시한다. 2026-11-03 사용자의 정책 선택에 따라 기본은 roots-adaptive/1, KST 04시다. 회상 결과·실제 경과 시간·시험 임박을 반영하고 이전 fixed 정책과 회차는 원래 값으로 보존한다. 자세한 규칙과 예시는 policy-examples.md를 따른다.

## 설정과 자료

STUDYEZ_ROOT_LEARNING_ENABLED=true와 강의별 enabled/검토된 활성 판/허용 계정이 모두 필요하다. 기본은 닫혀 있다. STUDYEZ_ROOT_POLICY로 명시적인 정책 판을 지정할 수 있으며 미지정 시 roots-adaptive/1을 사용한다. 이전 intervals 형식도 보존하여 읽는다. 새 정책 형식은 policy.py validate_policy와 policy-examples.md를 따른다. 이는 운영 활성화 승인이나 콘텐츠 검토를 대신하지 않는다.

roots/1 등록 형식은 tests/contracts/root_fixture.py의 합성 예제와 순수 validate_document를 참조한다. review.bank_sha256은 저장할 bank_snapshot의 canonical JSON SHA256이다. quizbank 참조는 실제 현재 DB의 은행/빌드와 일치해야 한다. sources 지문은 관리자 제공 검토 묶음의 출처 주장이다. 서버의 구조 검사가 실제 원본 PDF와 의학 답의 내용 검토를 대신하지 않는다.

콜린성 기존 15목표 후보, 연결 학습 10묶음, 49문항은 자동 채택·변환하지 않았다. 원래 은행/내용/검수 기록을 보존한다. 검토된 실제 콘텐츠 등록·운영 DB 준비·활성화는 별도 절차다.

## 검사

scripts/check_root_learning.py --check <required_check>는 state.json의 9개 검사 이름에 대응한다. 서버는 파일별 독립 프로세스/격리 DB, 브라우저는 새 합성 DB와 소유 서버 8027/5193만 사용한다. fixture의 의료적 의미는 검증 대상이 아니다.
