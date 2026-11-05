source-assessment/2. 별도 원본 검수 세션에서 원본 전체·현재 brief·문항·실제 stimulus PNG를 대조한다. 원본/기출의 잘못된 그림·정답·수치 자체를 올바른 의학 답으로 승인하지 않는다. 고정 입력을 다시 작성하지 않고 의미 판단 JSON만 반환한다.

questionFronts는 실제 학습자에게 보이는 발문이며 cloze 정답은 마스킹돼 있다. raw BANK의 cloze 저작 표기 속 정답을 발문 제공으로 오인하지 않는다. 반대로 실제 보이는 이름·선지·그림의 답 주석은 provided다. stimulusFiles의 각 정확한 PNG를 직접 열어 해당 문항의 실제 시각 자극으로 판독한다. 원본 전체 쪽을 문항 자극 crop으로 대신하지 않는다.

question_reviews와 direction_checks는 모든 실제 ID를 정확히 한 번 포함한다. tested/provided/explanation은 실제 관계 역할이다. 방향이 맞지 않는 역식별/설명은 direction_ids=[]로 보존한다. broad relation의 일부 사실을 묻는다는 이유만으로 전체 condition/answer_scope가 시험됐다고 하지 않는다. 여러 문항의 합집합과 한 문항 전체 회상을 구별한다.

각 direction_checks의 scope_status는 cue·answer_scope·components·relation_ids가 실제로 같은 전체 목표인지 consistent/conflict/unknown으로 판정한다. answer_scope의 필수 요소가 components에서 빠졌으면 map_fix다. components 목록 자체를 무조건 올바른 완전 목록으로 가정하지 않는다.

direction_evidence는 방향의 회상을 검토하는 각 후보 문항마다 작성한다. 그 방향의 모든 components를 정확히 한 번 포함한다. location=answer는 실제 질문이 요구하고 정답의 answer_units에 존재하는 경우이며 해당 0-based answer_unit_indices를 적는다. 발문/선지/그림이 답을 제공하면 provided, 해설에만 있으면 explanation, 확실히 묻지 않으면 missing, 근거상 판단 불가면 unknown이다. answer 외에는 indices=[]다. 표·문항·해설에 존재한다는 사실만으로 회상을 승인하지 않는다. 코드가 한 문항의 모든 요소가 answer인지 검사하며 부분 문항들을 합쳐 완성하지 않는다. visual_verdict는 실제 자극이 필요·존재·식별 가능하고 답 주석/오류가 없는지 ok/doubt/wrong/not_applicable로 판단한다. 이미지와 답의 좌우/기호/결합이 일치하는지 직접 실제 PNG를 연다. 이 검수와 독립 정답 검수에 동일 PNG가 첨부된다.

relation_checks는 모든 관계의 원본·임상 지지 여부 supported/conflict/unknown을 정확히 한 번 판정한다. 초기 unreviewed 상태와 별개이며 미확인은 자동 승격하지 않는다. target_checks는 모든 목표의 중요도 근거가 현재 의미에 맞는지 consistent/conflict/unknown을 정확히 한 번 판정한다. 원래 강조를 비동등 재정의에 전이하지 않는다. prerequisite_checks는 BANK의 모든 기존 question_id→prerequisite_id 쌍에 supported/unnecessary/unknown과 실제 이유를 정확히 한 번 기록한다. 내용상 필요한 최소 기초와 과도한 전체 표/목록 잠금을 구별한다.

clinical_context_status는 별도 clinical_conflicts가 원래 모든 source_conflicts의 의학적 충돌 사실을 보존하며 과거 검수 판정·저작 이력을 포함하지 않는지, 문제/답/해설에도 과거 판정이 섞이지 않는지 consistent/conflict/unknown으로 판단한다. 임상 충돌을 삭제해 blind 검수의 정오 판단을 왜곡하지 않는다.

issues는 구조화된 목록이다: question_fix(수정 가능한 문항/필요 선행 오류), map_fix(지도/중요도/정의 오류), required_gap(확인된 필수 직접 회상 누락), optional_extension(선택적 확장/미시험), limitation(자료/근거/의학적 불확실성), confirmation(긍정적 보존·범위 확인). 모든 항목에 고유 issue_id, 실제 text와 관련 question_ids/direction_ids를 작성한다. 불확실성을 필수 누락으로 오인하지 않는다. 다음 강의·타 교수·참고 범위·비학습 자료의 제외도 원본 전체에서 확인한다. 임상 정답만 정상이어도 목표 회상이 빠졌으면 별도로 지적한다. JSON만 반환한다.

required_gap은 실제 requirement=required인 direction_ids를 하나 이상 명시한다. 아직 지도에 없는 기초/목표 누락은 map_fix로 기록하고 없는 방향 ID를 만들지 않는다. optional·undecided 방향을 required_gap으로 잘못 분류하지 않는다.
