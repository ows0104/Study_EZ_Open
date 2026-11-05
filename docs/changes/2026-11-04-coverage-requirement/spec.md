# 계약

covered는 계속 하나 이상의 required 방향이 모두 confirmed이고 undecided 방향이 없어야 한다. confirmed/partial/missing/unknown 방향별 분류와 모든 관계 검증은 그대로다. 포인트 unknown은 실제 unknown 방향이 있거나, 관련 방향의 필수 여부가 undecided이거나, required 방향이 전혀 정의되지 않은 경우만 허용한다. required가 모두 결정된 일반 포인트에서 근거 없는 unknown은 계속 거절한다.

compiler는 실제 관계에 근거한 방향 분류를 먼저 계산한다. 기존 covered/partial/gap/실제unknown을 그대로 적용하고, 모두 확인됐지만 필수성 때문에 완전 충족을 정의할 수 없는 유효 입력만 포인트 unknown으로 내보낸다. 이유에 필수성/필수 방향 미정임을 명시한다. 모델 원문·관계 역할·회상 결과·verdict·문항·지도 requirement는 변경하지 않는다. 임의의 requirement 승격/방향 미확인 처리나 내용 제외를 하지 않는다.

새 모델 호출은0회다. 완료된 콜린성 원본 대조 원문/사용량과 첫 조립 실패 기록을 보존하고, 별도 기술 조립 증거를 붙여 같은 원문을 재조립한다. 원래 capped 시범과 운영 학습은 변경하지 않는다. 일반 strict AUDIT/roots의 기타 규칙은 유지한다.
