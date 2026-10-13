<!--
Bank Builder 프롬프트 — 정본
Version: 1.33
1.33 (2026-10-13) 설명·근거·통계의 반복을 줄이고 출제 결과 표만 간결하게 출력한다.
1.32 (2026-10-13) 웹은 문항·선지·정답을 출제하고 해설은 CLI에서 작성·검수한다.
1.31 (2026-10-13) 출제 포인트를 구체적인 인출·판단 목표로 적도록 명시한다.
1.30 (2026-10-13) 완성된 표 전체를 대화 본문으로 출력하도록 명시한다.
1.29 (2026-10-13) 출제 규칙을 간결하게 정리하고 웹 출제 포인트 계획과 CLI 검수를 연결한다.
-->
첨부한 강의자료와 족보로 의대 시험 대비 문제은행을 만들어줘.
강의: {{title}}

1. 교수 강조·학습목표·족보를 참고해 출제 포인트를 먼저 정리하고, 이를 바탕으로 Concept Map → Retrieval Plan → Question Bank를 작성해라. 문항 수와 형식은 각 포인트의 학습 가치에 맞게 판단해라.
2. 한 문제는 명확한 인출 또는 판단을 요구해야 한다. 단답형의 답은 용어·수치·짧은 관계로 쓰고, 나열·대응·과정·문맥에 맞는 형식을 선택해라.
3. 중요한 사실·조건·예외를 충분히 다루되, 같은 인출이나 판단을 형식·표현만 바꾸어 반복하지 마라. 회상과 비교·적용이 서로 다른 학습 목표라면 함께 출제할 수 있다.
4. 객관식을 적절히 활용해라. 먼저 답을 인출하는 기억 확인형은 recall_first, 선지를 비교·판별하는 과정이 목표인 구별·판단형은 comparison이다. 두 유형 모두 실제 선지와 정답을 작성해라.
5. 발문에 답을 노출하지 말고, 답의 범위를 결정하는 조건은 명확히 제시해라. answer_units는 핵심 채점 단위로 나누고, 필요한 기초 문항을 prerequisites로 연결해라.
6. 중요도와 난이도를 독립적으로 판단하고 Core·Advanced·Optional을 구분해라. 형식만으로 tier를 정하지 마라.
7. 각 포인트와 문제에 원본 근거를 남겨라. PDF는 실제 쪽 번호를 써라. 외부 의학지식도 사용하되 자료에 없거나 다른 내용은 EXT로 표시해라. 출처가 충돌하면 한 문항으로 합치고 차이·선택한 답·판단 근거를 설명해라.
8. 완성본을 검토해 누락·오류·중복을 수정해라. 정답이나 범위를 확정할 수 없는 내용은 불확실한 것으로 남겨라.

출력 형식

파일 링크 대신 이 대화 본문에 아래 표만 출력해라. 서론·자료 요약·표기 안내·별도 검토 보고는 생략하고 각 표는 한 번만 쓴다.

첨부 자료의 ID와 파일 이름은 다음과 같다. 이 ID를 source_refs에 사용한다.
{{sources}}
다음 이름의 Markdown 표를 출력한다. 각 표의 열 순서는 아래와 같다.
배열 항목은 <br>로 구분한다. 셀 본문의 |는 &#124;로 쓰고 한 행에 실제 줄바꿈을 넣지 않는다.

0. Exam Point Plan
point_id | point | source_refs
포인트 ID는 P001…로 지정한다.
각 포인트에는 무엇을 인출·구별·적용해야 하는지 구체적으로 적어라.

1. Concept Map
concept_id | title | graph_title | core_facts | importance | importance_rationale | concept_difficulty | tier | exam_signal_strength | related_concepts | source_refs
importance·concept_difficulty는 1–5, tier는 Core / Advanced / Optional, exam_signal_strength는 low / medium / high다.
graph_title은 개념을 구분할 수 있는 짧은 이름이다. core_facts는 핵심 관계만 짧게, importance_rationale은 중요도 판단 근거만 짧게 쓴다. core_facts·related_concepts는 ;로 구분한다.

2. Retrieval Plan
concept_id | directions | repetition_budget | target_mastery
directions는 direct / reverse / mechanism / discrimination / integration / sequence / trap 중 필요한 것을 선택한다.
repetition_budget는 1–100, target_mastery는 0.1–1이다.

3. Question Bank

3.1 Questions
question_id | concept_id | tier | importance | item_difficulty | format | retrieval_direction | mcq_mode | question | answer | answer_units | prerequisites | source_refs | exam_rationale | conflict_id
importance·item_difficulty는 1–5다. format은 basic / cloze / list / ox / mcq / multi_select / matching / sequence다.
mcq_mode는 recall_first / comparison이며 다른 형식은 none이다. exam_rationale에는 관련 point_id만 적고 포인트 설명을 반복하지 않는다.
cloze는 관련 빈칸 1–4개를 모두 {{c1}}로 표시한다. answer_units는 빈칸 등장 순서대로 대응시키고, answer에는 정답을 채운 문장을 쓴다.
basic의 answer와 answer_units는 같은 짧은 정답 단위다. ox의 answer는 O 또는 X다.
해설은 CLI에서 작성하므로 웹에서는 정답과 핵심 채점 단위만 출력한다.
integration에는 실제 필요한 기초 question_id를 prerequisites로 연결한다. 빈 prerequisites·conflict_id는 —로 쓴다.

3.2 Choice Details
question_id | options | correct_option_ids
options는 A: 내용<br>B: 내용…으로 쓴다. mcq는 정답 1개, multi_select는 해당하는 정답을 모두 적는다.

3.3 Matching Details
question_id | matching_left | matching_right | answer_pairs
왼쪽은 1. 항목…, 오른쪽은 A. 항목…으로 쓰고 정답 짝은 1. 왼쪽 - B. 오른쪽처럼 적는다.

3.4 Sequence Details
question_id | sequence_items | correct_order
항목에 A: 내용…처럼 ID를 붙이고 correct_order에 ID를 순서대로 적는다.

같은 판단의 보기 조합을 바꿀 가치가 있으면 선택적으로 다음 두 표를 작성한다.
3.5 Option Pools: question_id | pool_id | select_count | correct_when
3.6 Option Pool Candidates: question_id | pool_id | candidate_id | true_text | false_text | source_refs
각 후보는 동일 조건의 참·거짓 쌍을 갖는다. 풀별 후보는 최대 16개, select_count는 후보 수보다 적은 2–8개다.
correct_when은 참을 고르면 true, 거짓을 고르면 false다. 서로 다른 비교·판단이 필요하면 별도 문항으로 만든다.

4. Source Conflicts
conflict_id | description | source_refs | unresolved

5. Final Statistics
총 문제 수, tier별 수, 출처 충돌 문항 수, EXT 문항 수만 한 줄로 적는다.

문항 ID는 모든 표에서 일치해야 한다. 해당 형식이 없는 상세 표는 생략한다.
마지막 줄: STUDYEZ_BANK_COMPLETE
