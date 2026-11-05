learning-brief/2. 원본 또는 명시적으로 제공한 Concept map·포인트를 정규화한다. source inputMode라면 원본 전체만으로 독립 추출하고 independent_points=confirmed, 제공 목록을 정규화하면 derived다. 강의/교수/올해 범위·색상 제외·족보 범위를 보존하고 목록 밖 누락도 확인한다. 원본 그림이나 표의 존재를 정확성 보증으로 삼지 않는다. 임상 오류·불확실한 수치·과도한 일반화는 충돌·한계로 기록한다.

각 direction은 일관된 하나의 회상 목표다. components에는 그 answer_scope를 충족하려면 실제 답해야 할 모든 핵심 요소를 안정적인 component_id와 짧은 text로 명시한다. 한 요소마다 문항/목표를 새로 만들지 않는다. 예컨대 조건·결과·적용 한계가 scope에 있으면 각 요소를 모두 포함한다. 범위의 일부를 뒤의 해설로 미루고 전체 방향을 준비로 계산할 수 없다. 단순 안내·검수 지시를 학생 암기 목표로 만들지 않는다. requires_visual은 실제 그림을 보고 읽는 것이 목표인지 표시한다. 시각 식별을 언어적 정의 회상으로 대체하지 않는다.

방향의 cue·answer_scope·components·relation_ids가 같은 범위를 가리키는지 교차 확인한다. 처음부터 과도하게 넓은 주제 관계에 여러 사실을 묶거나 같은 사실을 중복 목표로 계산하지 않는다. 전체 비교 목표가 원본/임상 근거를 넘어가면 정직하게 한정한다. 중요도는 해당 회상 요소의 구체적 근거로 판단하며 관련 약물명/주변 문구의 강조를 자동 전이하지 않는다. 실제 필요한 선행 관계만 작성하며 근거 없는 전체 표/약물 목록을 잠금으로 요구하지 않는다.

원본 관계의 확인 여부인 review_status와 이후 독립 검수의 판단은 별개다. 미확인은 unreviewed로 남겨도 되며 이후 원본 검수의 명시적 relation_checks로 채택 여부를 결정한다. sources는 입력 재고를 정확히 복사한다. JSON만 반환한다.

prerequisites의 relation_id는 kind=prerequisite인 관계만 가리킨다. 그 from_id는 before_target의 concept_ids에, to_id는 after_target의 concept_ids에 있어야 한다. association/comparison을 선행 관계 대신 사용하지 않는다. 실제 원본이 뒷받침하는 필요한 순서만 만들고, 선행 관계의 순환이나 목표/관계 끝점의 오접속을 점검한다. 독립 검수 전이므로 필요하면 review_status=unreviewed를 유지한다.
