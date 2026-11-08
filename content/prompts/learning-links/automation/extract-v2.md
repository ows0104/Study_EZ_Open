learning-brief/2. 원본 또는 명시적으로 제공한 Concept map·포인트를 정규화한다. source inputMode라면 원본 전체만으로 독립 추출하고 independent_points=confirmed, 제공 목록을 정규화하면 derived다. 강의/교수/올해 범위·색상 제외·족보 범위를 보존하고 목록 밖 누락도 확인한다. 원본 그림이나 표의 존재를 정확성 보증으로 삼지 않는다. 임상 오류·불확실한 수치·과도한 일반화는 충돌·한계로 기록한다.

신규 출력에 recall_policy="recall-units/1"을 쓴다. 학습목표의 내용 범위와 한 번에 답할 회상 단위를 구분한다. components는 실제 배울 핵심 내용이며 원본 해석의 주의사항·기출 대응 설명·검수상 한계는 notes/scope 기록에 둔다. 그 자체가 의학적으로 유의미한 학습 목표이면 별도 회상·판단으로 설계한다.

각 direction은 일관된 학습목표다. 함께 기억할 가치와 회상 부담에 따라 여러 문항으로 구현할 수 있다. 넓은 목표를 분산 구현할 때 recall_units에 unit_id/cue/answer_scope/component_ids/relation_ids를 작성한다. 각 unit은 한 번의 명확한 회상이며 모든 components를 빠짐·중복 없이 나누고 원래 관계 범위를 유지한다. unit_id는 전체 방향·단위에서 고유하다. 짧은 같은 범주 목록·하나의 기전/과정은 묶을 수 있고, 독립 요구·많은 대응 축은 나누거나 표 등으로 구조를 제공한다. 개수의 고정 상한 대신 답의 양·비교 축·조건·채점 부담으로 판단한다. 충분히 작은 방향이나 실제 종합 판단은 recall_units 없이 유지한다. 여러 사실의 개별 회상만으로 종합 판단을 확인했다고 하지 않으며, 필요한 종합 판단은 실제 사례/검사 결과 등 별도 방향으로 남긴다.

requires_visual은 실제 그림 식별 목표인지 표시한다. 표 채우기의 텍스트 표 자체를 원본 시각 식별로 간주하지 않는다. 실제 시각 목표를 언어 정의로 대체하지 않는다.

방향의 cue·answer_scope·components·relation_ids가 같은 범위를 가리키는지 교차 확인한다. 처음부터 과도하게 넓은 주제 관계에 여러 사실을 묶거나 같은 사실을 중복 목표로 계산하지 않는다. 전체 비교 목표가 원본/임상 근거를 넘어가면 정직하게 한정한다. 중요도는 해당 회상 요소의 구체적 근거로 판단하며 관련 약물명/주변 문구의 강조를 자동 전이하지 않는다. 실제 필요한 선행 관계만 작성하며 근거 없는 전체 표/약물 목록을 잠금으로 요구하지 않는다.

원본 관계의 확인 여부인 review_status와 이후 독립 검수의 판단은 별개다. 미확인은 unreviewed로 남겨도 되며 이후 원본 검수의 명시적 relation_checks로 채택 여부를 결정한다. sources는 입력 재고를 정확히 복사한다. JSON만 반환한다.

prerequisites의 relation_id는 kind=prerequisite인 관계만 가리킨다. 그 from_id는 before_target의 concept_ids에, to_id는 after_target의 concept_ids에 있어야 한다. association/comparison을 선행 관계 대신 사용하지 않는다. 실제 원본이 뒷받침하는 필요한 순서만 만들고, 선행 관계의 순환이나 목표/관계 끝점의 오접속을 점검한다. 독립 검수 전이므로 필요하면 review_status=unreviewed를 유지한다.

제공된 Concept map이 concept-map-extract/3이면 Map의 concept_id를 그대로 쓰고, 각 개념의 parent_id를 해당 개념의 parent_ids에 그대로 포함해 강의의 갈래 구조를 보존한다. 세부 사실 노드는 해당 Map 개념 아래에 둔다. 갈래를 넘는 연결과 구조를 묻는 목표(root/branch)는 Map의 relations를 근거로 만든다.

importanceTable이 있으면 targets[].importance의 세 축은 모두 status=unreviewed, evidence=[]로 둔다. 중요도는 출제 포인트 근거로 조립 때 계산하며, 정규화는 근거를 목표에 옮겨 적지 않는다.
