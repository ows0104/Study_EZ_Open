# Review · 간소화한 Map/포인트 추출 /2

기준 revision a3f67d13, 브랜치 codex/map-point-prompts. 사용자 제공의 예전 포인트/Concept Map/Retrieval Plan은 참고 자료로만 사용했다. 최종 /2는 이전 상세 /1 초안의 수집 부담을 줄이며, /1은 Git 이력에 보존한다.

## 최종 변경

- Map: overview, concepts(concept_id/title/core_facts/source_refs), relations(from_id/to_id/relation/source_refs), notes. 고정 계층·문항 평가 없이 원본의 개념·관계·큰 흐름에 집중한다.
- 포인트: points(point_id/point/source_refs), notes. point에 실제 인출·구별·적용 목표와 필요한 방향·조건을 적는다. 독립 회상 목표와 의미 있는 묶음의 균형을 유지한다.
- 공통 헤더는 schema_version/title이다. 원본 메타데이터 재작성·관계별 유형/지지 판정 장부·필수 방향 목록/답 요소 분해·중요도/난도 점수·복습량·목표 숙련도는 수집하지 않는다.
- 실제 UTF-8 concept-map.json / exam-points.json 작성과 다운로드 링크 제공을 요청한다. 이 지시가 실제로 수행되는지 모델 호출·다운로드 검증을 한 것은 아니다.
- 중요 불확실성·자료 충돌·미확인 범위는 notes에 남긴다. 원본 근거는 source_refs의 입력 ID와 물리 쪽/위치로 연결한다. 참조 원본의 메타데이터는 입력 재고가 소유한다.

## 검증

개발용 verify_formats.py에서 두 JSON Schema, 프롬프트 내 합성 예시 일치, 잘못된 필드/버전/참조/중복 ID/근거 위치/쪽수/빈 결과 등 16사례 거절을 확인한다. 중복 JSON 키도 거절한다. 여러 부모·교차 연결·비계층 순환, 미독해 이유가 있는 빈 결과 2사례, 페이지 대신 확인 가능한 locator는 수용한다. 관계의 의미와 분류 순환은 단순 relation 문장을 원본과 대조하는 후속 의미 검토에서 확인하며 기계 검증으로 인증하지 않는다.

이전 단계의 상세 /1 스키마 검사 및 기존 생성/런타임 16개·웹 프롬프트 7개 회귀 통과는 당시 로그에 보존한다. 이번 /2 변경은 두 프롬프트·미연결 출력 계약·개발용 검증에 한정되며 prompt-review를 새로 실행한다. git diff --check와 staged diff 확인도 수행한다. 이전 Python 임시 경로/웹 TypeScript 의존성 환경 오류 및 해결 기록은 Git 이전 판에 보존한다.

## 적용 범위와 한계

자동 런타임 연결·응답 수신/저장·화면·호출 분리·후속 대조는 미구현이다. 현행 통합 추출 및 learning-brief/2/PLAN 계약, 운영 DB/문항/학습/원장/검수 상한은 유지한다. 모델 호출·출제 재개·운영 배포 없음. 기존 중단 요청 548은 재개하지 않았다. 형식 검사는 모델의 의학적 정확성·전체 원본 확인·실제 파일 작성 성공을 인증하지 않는다. 복원은 이번 프롬프트/형식/안내만 되돌린다.
