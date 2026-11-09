root-generation/2 임상 충돌 정리 확인 단계다. 출력은 clinical_context_status, clinical_context_problem, clinical_context_reason 셋이다.

독립 정답 검수에는 문항·정답·해설과 별도의 clinical_conflicts만 전달된다. 이 단계는 그 전달 내용이 안전한지만 판정한다. 확인할 것은 세 가지다.
- clinical_conflicts가 BANK source_conflicts의 모든 conflict_id에 대해, 원본(material/*.md·PNG)에 실제로 있는 의학적 충돌 사실과 현재 정답의 관계를 빠짐없이 담았는가
- clinical_conflicts에 과거 검수 판정·검수자 판단·수정 차수·중요도가 섞이지 않았는가
- 문제·정답·해설에 과거 판정이나 저작 이력이 섞이지 않았는가
  (정답 검수자가 읽는 칸만 본다. exam_rationale처럼 저작용 칸의 이력은 contamination이 아니다.)

모두 맞으면 consistent다. 원본과 다르거나 빠졌거나 과거 판정이 섞였으면 conflict이고, reason에 어느 conflict_id 또는 question_id인지와 고칠 내용을 적는다. 원본을 확인할 수 없으면 unknown이다. clinical_conflicts와 source_conflicts가 모두 비어 있으면, 원본에 의학적 충돌이 실제로 없는지 확인해 판정한다.

문항의 학습 가치·중요도·정답의 의학적 정오는 이 단계에서 판정하지 않는다. 정오는 독립 정답 검수의 몫이다. JSON만 반환한다.

clinical_context_problem은 conflict의 종류다. 정답 검수를 막을지가 이것으로 정해진다.
- contamination: clinical_conflicts나 문제·정답·해설에 과거 검수 판정·검수자 판단·수정 차수·중요도·저작 이력(포인트·문항 ID나 「보완」 경위)이 섞였다. 정답 검수를 막는다.
- incomplete: 오염은 없지만 충돌 사실이 빠졌거나, 출처·쪽수가 틀렸거나, 원본과 다르게 전달됐다. 정답 검수는 그대로 진행하고 다음 보완에서 고친다.
- none: consistent 또는 unknown일 때.
둘 다 있으면 contamination이다. reason에는 지금처럼 어느 ID인지와 고칠 내용을 적는다.
