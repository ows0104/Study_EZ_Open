공통 root-generation/2 저작/보완 단계다. 출력은 bank, brief, visual_stimuli, clinical_conflicts, map_change_reason의 지정 JSON이다. 최초 웹 응답이 있으면 먼저 그 전체 유효 ID·문항·답·해설을 보존하여 정리하며 CLI 최초 대체 출제를 하지 않는다. generate에서는 initialBriefErrors가 비어 있으면 초기 brief를 그대로 반환한다. initialBriefErrors가 있으면 최초 지도 구조 교정으로 이미 총3회 중1회를 사용했다. 원본·범위·출제포인트 text/scope/ID·exclusions를 보존하면서 지도 전체의 실제 참조·선행 구조 오류를 함께 바로잡고 map_change_reason을 명시한다. 문항을 함께 본 이 지도는 independent_points=derived다. 기존 문항의 원문 보존은 유지하며 추가 내용 보완은 독립 검수 이후 남은 횟수에서 수행한다.

prerequisites의 relation_id는 반드시 kind=prerequisite인 별도 관계여야 한다. from_id는 before_target의 concept_ids 안에, to_id는 after_target의 concept_ids 안에 있어야 한다. association/comparison 관계를 선행 근거로 재사용하거나 반대 끝점을 참조하지 않는다. 미확인 관계는 unreviewed로 남겨도 되며 이후 독립 원본 검수의 판단으로만 채택한다. 순환·중복·불필요한 잠금을 만들지 않는다.

repair는 문항뿐 아니라 진단된 지도 오류도 수정할 수 있다. 이전 brief와 원문 포인트 text/scope·scope·sources·exclusions는 보존한다. 조건·관계·방향·선행을 바꾸는 경우 map_change_reason에 무엇이 왜 바뀌었는지와 이전 목표와의 비동등성을 적는다. 문항을 본 뒤 수정한 지도는 independent_points=derived다. 이전 독립 추출 완료 기록을 현재 수정본의 독립성으로 옮기지 않는다. 동일 ID의 변경도 새 의미 검토가 필요하다. 바뀐 목표의 중요도 근거를 다시 검토하고 이전 강조를 자동 승계하지 않는다. 준비율을 올리려고 필수 components를 없애거나 설명에 숨기지 않는다.

원본·검수의 실제 question_fix/map_fix/required_gap만 우선 보완한다. optional_extension/limitation/confirmation은 자동 확장/반복 저작 사유가 아니다. 의심0을 목표로 하지 않는다. 기존 문항을 먼저 쓰고 새 문항은 독립 목표와 이유를 audit_summary.changes에 기록한다. 바뀌지 않은 문항은 그대로 보존한다. 각 문항은 해당 방향의 필요한 components를 모두 실제로 답하게 하며 정답을 발문이나 그림 주석에 노출하지 않는다. 해설은 실제 답한 사실의 대용이 아니다. prerequisites는 실제 필요한 문항만 연결하고 순환·없는 ID를 만들지 않는다. 기존 강의 흐름과 선행 순서가 맞는지 확인한다.

visual_stimuli는 실제 원본 PDF의 question_id/source_id/물리쪽/page/정규화 crop[left,top,right,bottom]/reason의 완전한 목록이다. 필요한 원본 그림을 직접 열고 선택한다. pagenum·bbox·그림과 답의 위치/방향이 맞는지 확인한다. 이름·정답 표시·불필요한 표 주석을 자르되 필요한 구조/기호는 보존한다. 임의로 그리거나 이미지 경로/바이너리를 작성하지 않는다. 코드가 이 crop을 렌더해 동일 PNG를 원본검수·독립정답검수·학생 화면에 제공한다. 실제 시각 목표에는 실제 이미지를 붙인다. 원본 그림 오류는 사용하지 말고 검증 가능한 원본 대체와 충돌 기록을 남긴다.

clinical_conflicts는 BANK source_conflicts의 모든 conflict_id마다 facts를 가지며 실제 원본의 충돌 주장과 현재 의학 답의 관계만 명시한다. 과거 sourceAudit/medical verdict, 검수자 판단, 수정 차수, 중요도는 넣지 않는다. 의학적으로 필요한 충돌 사실은 누락하지 않는다. 과거 판정·수정 이력은 audit_summary.changes 등 별도 기록에 보존하며 문제/답/해설/clinical_conflicts에 섞지 않는다. 독립 원본 검수가 이 projection과 정본의 일치·완전성을 확인하고 정답 검수는 이 의학적 내용만 받는다.

webBank가 제공되면 이미 원문 JSON을 코드로 변환한 BANK다. 이를 그대로 사용하고 개념·학습 위치·실제 선행 연결 및 원본 그림만 연결한다. 문항 내용·정답·선지·출처·중요도·심화·순서를 다시 작성하지 않는다. clinical_conflicts는 보존된 충돌에 맞춰 작성한다.

option_pools는 빈 배열이다. 실제 범위/안전한 조건/외부 근거·불확실성을 보존한다. JSON만 반환한다.
