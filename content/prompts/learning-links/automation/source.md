source-assessment/1 · 독립 세션에서 원본 전체·Concept map·출제포인트와 최종 문항을 대조한다.
출력은 schema_version, summary, question_reviews, direction_checks, input_issues다. 고정 지도·포인트·hash·coverage·충족 등급은 다시 작성하지 않는다. 코드가 불변 입력과 아래 의미 판단에서 조립·검증한다.
question_reviews는 BANK의 모든 문항을 정확히 한 번 포함한다. 원본 대조 verdict(ok/doubt/wrong), note, suggested_answer와 관련 relations를 기록한다. 불확실성은 임의로 통과시키지 않는다.
relations는 한 문항/관계당 한 번만 기록하고 역할을 단일 값으로 판단한다: 발문에서 주어진 관계 provided, 답을 내기 위해 실제 회상해야 하는 관계 tested, 해설에만 나오는 관계 explanation. 단지 언급되거나 제공된 관계는 tested가 아니다. 관련 없는 관계는 생략한다.
tested의 direction_ids는 그 관계를 실제로 회상시킨 방향만 선택한다. 출력 스키마는 해당 relation_id를 포함하는 실제 방향 ID만 허용한다. 역방향·유사한 발문·같은 주제라고 다른 방향을 대신 시험했다고 추정하지 않는다. 제공/해설 관계의 direction_ids는 빈 배열이다. 같은 관계에 다른 계획 방향이 있더라도 실제 cue가 어느 방향에도 맞지 않으면 tested와 이유를 보존하되 direction_ids=[]로 기록하고 계획의 누락을 input_issues에 남긴다. 빈 방향은 어떤 계획 방향에도 충족 근거가 되지 않는다.
direction_checks는 brief의 모든 방향을 정확히 한 번 포함한다. 원본·전체 문항과 직접 회상 관계를 끝까지 대조했으면 reviewed, 직접 시험 여부를 결정할 근거가 부족하거나 판단이 불확실하면 unknown이며 이유를 남긴다. 생략된 관계의 실제 미시험과 판단 불가를 혼동하지 않는다. reviewed는 충족됐다는 뜻이 아니다. 실제 tested 집합이 비면 missing, 일부이면 partial, 전체이면 confirmed를 코드가 계산한다. 한 문항에서 전체 방향을 시험하는지와 여러 문항의 합집합은 구분하며 실제 시험한 관계만 지정한다.
목록 밖 누락·범위 오류·과분할·정규화 지도 자체의 오류·중요도 근거·첫 학습 순서·기초 회상 누락은 input_issues에 기록한다. 목표·포인트·제외 이유를 몰래 변경하지 않는다. 제외 포인트도 원본 전체 대조에서 확인한다. wrong·doubt·누락과 실제 원본 근거를 그대로 보존한다.
