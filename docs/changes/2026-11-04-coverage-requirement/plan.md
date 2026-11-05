# 구현 계획

studyez_contracts/learning_links/validate.py의 unknown 포인트 조건을 필수성 미결정과 분리하고, roots/source_assessment.py에 해당 표현과 이유를 추가한다. tests/contracts/test_source_assessment.py에 required/optional/undecided와 전체/부분/미시험/실제unknown 조합을 검사한다. 기존 covered, 방향 분류, 일대일 ID·hash·의학 판정 보존 규칙을 바꾸지 않는다.

검사는 contracts 전체, 관련 생성기 회귀, 격리 root_source_assessment/root_generation/root_web_generation/root_one_click/root_preservation/route_contract 및 같은 validate_review를 소비하는 오프라인 connection_plan/report로 한다. 실제 원문을 재조립해 P13과 D12의 필수성/회상 여부가 모두 보존되는지 확인한다. 테스트/리뷰 후 고정 API 계약만 기존 승인 범위로 배포·사후 확인한다.

콜린성 예시의 첫 실행 script/원장/실패/raw/usage를 그대로 두고 별도의 assemble_result.py로 완성한다. 부모가 임상 내용을 저작하지 않는다. 현재 사용자 '콜린성 약리학 자료로 수정된 흐름을 한 번 돌려 실제 결과물을 보여줘' 및 기존 '원인을 해결하자' 승인으로 이 구현을 진행한다. API 복원 기준은 studyez-api-release-1793760893095067800, DB/웹 변경과 콘텐츠 공개는 없다.
