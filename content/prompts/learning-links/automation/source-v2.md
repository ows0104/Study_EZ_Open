source-assessment/2. 별도 원본 검수 세션에서 원본 전체·현재 brief·문항·실제 stimulus PNG를 대조한다. 원본/기출의 잘못된 그림·정답·수치 자체를 올바른 의학 답으로 승인하지 않는다. 고정 입력을 다시 작성하지 않고 의미 판단 JSON만 반환한다.

questionFronts는 실제 학습자에게 보이는 발문이며 cloze 정답은 마스킹돼 있다. raw BANK의 cloze 저작 표기 속 정답을 발문 제공으로 오인하지 않는다. 반대로 실제 보이는 이름·선지·그림의 답 주석은 provided다. stimulusFiles의 각 정확한 PNG를 직접 열어 해당 문항의 실제 시각 자극으로 판독한다. 원본 전체 쪽을 문항 자극 crop으로 대신하지 않는다.

question_reviews와 direction_checks는 모든 실제 ID를 정확히 한 번 포함한다. tested/provided/explanation은 실제 관계 역할이다. 방향이 맞지 않는 역식별/설명은 direction_ids=[]로 보존한다. recall_units가 있는 목표는 여러 문항에 나뉜 단위별 실제 회상을 확인해 내용 충족을 집계한다. 각 단위의 cue/answer_scope/components/relation_ids가 같은 실제 회상 범위를 나타내는지 확인한다. units가 없는 종합 방향은 그 판단을 실제로 수행하는 한 문항의 전체 회상이 필요하다. 부분 사실의 합집합으로 종합 판단을 대신하지 않는다.

각 direction_checks의 scope_status는 cue·answer_scope·components·relation_ids가 실제로 같은 전체 목표인지 consistent/conflict/unknown으로 판정한다. answer_scope의 필수 요소가 components에서 빠졌으면 map_fix다. components 목록 자체를 무조건 올바른 완전 목록으로 가정하지 않는다.

direction_evidence는 방향의 회상을 검토하는 각 후보 문항마다 작성한다. 부모 방향의 모든 components를 정확히 한 번 포함하여 분할 문항이 맡지 않은 내용도 missing 등으로 정직하게 남긴다. location=answer는 실제 발문이 요구하고 answer_units에 존재하는 내용이며 0-based answer_unit_indices를 적는다. 발문/선지/그림이 제공한 내용은 provided, 해설에만 있으면 explanation, 묻지 않으면 missing, 판단 불가면 unknown이다. answer 외에는 indices=[]다. 코드는 명시 recall_unit마다 전체 실제 회상을 확인하고 모든 단위가 확인되어야 부모 내용 충족을 인정한다. 표의 행/열 안내와 실제 빈칸 정답을 구별한다. visual_verdict는 원본 그림의 필요·존재·식별·답 주석 여부를 판정하며 원본 시각 식별에 실제 PNG를 확인한다. 텍스트 cloze 표는 원본 그림 식별이 아니다.

recall_policy=recall-units/1이면 design_checks에 모든 문항을 정확히 한 번 포함한다: question_id, verdict(ok/doubt/wrong), reason. 실제 회상 목표를 짧게 요약하고 답의 양·독립 요구의 수·조건·채점 부담과 형식의 적절성을 검토한다. 단순한 글자 수 상한을 쓰지 않는다. 여러 요구가 과도하게 겹치면 분할이나 표/빈칸/대응/선택 등 구체적 개선 방향을 쓴다. 원본 일치나 문항 안의 지식이 맞다는 사실만으로 설계를 ok로 하지 않는다. 기출 정답 기억·검수 설명을 묻는 질문, 의도가 불분명한 후속 질문, 지식 없이 문구로 정답이 드러나는 판단은 wrong과 question_fix로 기록한다. 해설의 주의사항이 채점에 섞이면 역할에 맞게 옮긴다. 목표 자체가 지나치게 넓거나 units가 의미를 바꾸면 map_fix로 기록한다. 단순 표현 취향과 실제 설계 위반을 구별한다.

relation_checks는 모든 관계의 원본·임상 지지 여부 supported/conflict/unknown을 정확히 한 번 판정한다. 초기 unreviewed 상태와 별개이며 미확인은 자동 승격하지 않는다. target_checks는 모든 목표의 중요도 근거가 현재 의미에 맞는지 consistent/conflict/unknown을 정확히 한 번 판정한다. 원래 강조를 비동등 재정의에 전이하지 않는다. prerequisite_checks는 BANK의 모든 기존 question_id→prerequisite_id 쌍에 supported/unnecessary/unknown과 실제 이유를 정확히 한 번 기록한다. 내용상 필요한 최소 기초와 과도한 전체 표/목록 잠금을 구별한다.

clinical_context_status는 별도 clinical_conflicts가 원래 모든 source_conflicts의 의학적 충돌 사실을 보존하며 과거 검수 판정·저작 이력을 포함하지 않는지, 문제/답/해설에도 과거 판정이 섞이지 않는지 consistent/conflict/unknown으로 판단한다. 임상 충돌을 삭제해 blind 검수의 정오 판단을 왜곡하지 않는다.

issues는 구조화된 목록이다: question_fix(수정 가능한 문항/필요 선행 오류), map_fix(지도/중요도/정의 오류), required_gap(확인된 필수 직접 회상 누락), optional_extension(선택적 확장/미시험), limitation(자료/근거/의학적 불확실성), confirmation(긍정적 보존·범위 확인). 모든 항목에 고유 issue_id, 실제 text와 관련 question_ids/direction_ids를 작성한다. 불확실성을 필수 누락으로 오인하지 않는다. required_gap의 direction_ids에는 brief에서 requirement=required인 방향만 넣는다. 같은 누락에 optional 방향도 걸리면 그 방향들은 별도 optional_extension 항목으로 적는다. 방향에 대응하지 않는 누락은 map_fix다. 다음 강의·타 교수·참고 범위·비학습 자료의 제외도 원본 전체에서 확인한다. 임상 정답만 정상이어도 목표 회상이 빠졌으면 별도로 지적한다. JSON만 반환한다.

required_gap은 실제 requirement=required인 direction_ids를 하나 이상 명시한다. 아직 지도에 없는 기초/목표 누락은 map_fix로 기록하고 없는 방향 ID를 만들지 않는다. optional·undecided 방향을 required_gap으로 잘못 분류하지 않는다.

importanceTable과 targetImportance가 있으면 target_checks는 그 목표의 중요도 근거(포인트별 kind·quote·refs)가 원본과 맞는지 판정한다. 확인 내용은 세 가지다.
- 출제 예고·출제 제외 원문이 실제로 그 쪽에 있고 그 회상 단위를 가리키는가
- 기출 연도·번호가 그 회상 단위를 묻는가
- 강조 표시와 출처 판정이 실제 표시와 문장에 맞는가
맞으면 consistent, 원본과 다르면 conflict로 하고 map_fix에 고칠 근거를 적는다. 확인할 수 없으면 unknown이다. 범례·색상·스탬프는 필기자마다 다르므로 실제 표시와 문장을 우선한다. 같은 쪽·표의 다른 사실로 근거가 옮겨졌으면 conflict다. 문항의 point_ids가 실제 회상 내용과 맞지 않으면 question_fix다.
