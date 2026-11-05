# 설계

source 모델의 새 source-assessment/1 출력은 모든 문항의 원본 verdict/note/suggested_answer, 관계별 단일 역할(tested/provided/explanation), tested인 경우 실제 시험하는 방향 IDs, 모든 방향의 원본 대조 완료 여부(reviewed/unknown)와 이유, 입력 지적이다. 관계 배열은 해당 문항에 관련된 관계만 포함한다. 생략은 목표 충족 증거가 아니며, 실제 미시험과 판단 불가는 방향별 검토 상태로 구분한다.

입력 brief와 BANK로 생성하는 출력 스키마가 문항·관계·방향 ID를 실제 재고에 제한하고 tested 방향을 그 관계를 포함한 방향으로 제한한다. 역할은 한 문항/관계당 한 값만 허용한다. 중복·누락·없는 참조는 로컬에서도 검증한다. 문항/은행 해시와 불변 CORE는 코드가 복사·계산한다. 모델은 coverage나 hash를 작성하지 않는다.

순수 공용 compiler가 의미 판단을 그대로 보존해 기존 AUDIT 계약으로 조립한다. 방향 reviewed 여부와 실제 tested 집합만으로 confirmed/partial/missing/unknown을 계산하고, 제외 사유·필수/미결정 기준으로 포인트 상태를 집계한다. 제공/해설 관계는 tested로 바꾸지 않으며, 개별 문항이 방향 전체를 시험하는 과제만 기존 make_document가 채택한다. 모호한 요구사항 때문에 기존 coverage 계약으로 표현할 수 없으면 명확한 기술 오류로 보류한다. 기존 validate_review/validate_audit/validate_result를 느슨하게 만들지 않는다.

모델 raw assessment와 usage는 조립 전에 보존한다. 잘못된 참조·역할·누락 등 기술 실패는 source 단계 failed로 남기며 BANK repair를 호출하지 않는다. canonical AUDIT와 raw hash를 원장에 함께 묶고 최종 manifest에 마지막 raw를 보관한다. 소비자는 raw를 다시 compile해 sourceAudit와 정확히 일치하는지 검사한다. 과거 유효 AUDIT 결과는 기존 검증으로 계속 읽지만 새 생성기는 새 프로토콜만 받는다. 재개 시 raw/canonical 어느 하나라도 바뀌면 보류한다.

문항 수정 최대3/원본·정답검수 최대4와 기존 독립 정답 검수는 유지한다. 예전 시범 원장·원문·모든 판정·사용량은 보존하며 게시하지 않는다. 운영 DB를 테스트에 사용하지 않는다.
