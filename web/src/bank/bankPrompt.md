<!--
Bank Builder 프롬프트 — 정본
Version: 1.1

이 파일이 ChatGPT에 가는 프롬프트의 정본이다. 이 주석은 보내지 않는다.
{{…}} 자리는 web/src/bank/prompt.ts 가 강의마다 채운다. {{c1}} 같은 cloze 표기는 그대로 간다.
고치면 아래에 판을 하나 올리고 Version 을 같이 올린다. 서버에 응답이 저장될 때 이 Version 이 같이 남는다.

1.1 이사 (2026-10-04)  AdaptiveStudy3/bank_builder/bank_prompt.md 에서 이리로 옮겼다 — 사이트에서
                   만들게 되면서. 내용은 그대로다. 그쪽 파일은 「이사했다」만 남긴다.

1.1 (2026-10-04)  v1.0(저장소 루트 Bankbuilder_v1.0.md, 기록으로 둔다)의 §1–8을 옮겨 왔다.
                   §3에 「Cloze 작성법」 — 빈칸 여럿 허용, 핵심 개념을 비운다, 축은 남기고 답은 남기지 않는다,
                   나열은 List로. quizgen/prompts/core/quality.md의 cloze 규칙에서 골랐다.
                   §5에 「Source page/slide」 — PDF 실제 쪽 번호, 여러 쪽이면 각각(슬라이드 이미지를 붙이려고).
                   §9를 앱이 읽는 열·필드 이름으로 고정하고, 강의 설정 칸을 넣었다.
-->
첨부한 **올해 필기/강의자료와 족보만**을 근거로 의대 시험 대비용 question bank를 만들어줘.

외부 의학지식은 사용하지 말고, 자료에 없는 내용을 보충하거나 교정하지 마.

강의자료와 족보가 서로 충돌하면 임의로 하나를 고르지 말고, **source conflict로 표시해서 각각 따로 보존**해.

목표는 강의의 모든 사실을 카드화하는 것이 아니라,

> **시험일까지 중요한 내용을 정확하고 다양한 방향으로 회수할 수 있는 question bank를 만드는 것**

이다.

다음 순서로 작업해줘.

# 1. Concept Map

먼저 강의를 concept 단위로 나눠라.

각 concept에 다음을 붙여라.

- Concept ID
- Concept name
- Importance: 1–5
- Concept difficulty: 1–5
- 중요도 근거
- 필요한 retrieval directions

Importance와 difficulty는 독립적으로 평가해라.

Importance를 판단할 때 특히 다음을 반영해라.

- 교수 직접 강조
- 학습목표
- take-home message
- 족보 반복
- 최근 족보 직접 출제
- 여러 슬라이드에 걸친 상세 설명
- 다른 개념의 prerequisite 여부

족보에서 반복된 granular fact는 큰 개념에 묻혀 삭제하지 마라.

단, 슬라이드에 존재한다는 이유만으로 모든 세부사항을 같은 비중으로 문제화하지 마라.

낮은 중요도의 내용은 삭제할 필요는 없지만, 필요한 경우 Optional로 보내라.

# 2. Retrieval Plan

각 concept마다 실제로 어떤 방향으로 회수해야 하는지 정해라.

가능한 retrieval direction:

- direct
- reverse
- mechanism
- discrimination
- integration
- sequence
- trap

중요도가 높을수록 필요한 경우 여러 retrieval direction을 사용해라.

하지만 모든 concept에 기계적으로 direct/reverse/integration을 전부 만들지는 마라.

저중요도 concept은 direct recall 정도로 충분할 수 있다.

같은 사실을 여러 문제로 만들 경우에는 단순 wording 변화가 아니라 **retrieval direction 자체가 달라야 한다.**

예:
- drug → target
- target → drug
- mechanism → drug
- similar drugs discrimination
- mechanism integration

# 3. Question Bank

Concept Map과 Retrieval Plan을 바탕으로 문제를 만들어라.

사용 가능한 형식:

- Basic
- Cloze
- List
- O/X
- MCQ
- Multi-select
- Matching
- Sequence

문제 수는 미리 정하지 말고, 강의의 양·중요도·족보 밀도에 따라 결정해라.

## 문제 설계 원칙

- 한 문제는 **하나의 명확한 retrieval act**를 중심으로 한다.
- 질문을 읽었을 때 무엇을 회상해야 하는지 즉시 알 수 있어야 한다.
- 난이도는 애매한 발문으로 올리지 말고 reverse, mechanism, discrimination, integration으로 올린다.
- 같은 사실을 거의 같은 방향으로 반복하는 문제는 만들지 않는다.
- 중요한 concept은 필요하면 direct → reverse → mechanism/discrimination → integration으로 확장한다.
- integration 문제는 atomic fact를 대체하지 않고 그 위에 추가한다.
- Cloze는 아래 「Cloze 작성법」을 따른다.
- List는 약물명, 효소, 구조, 숫자, 순서처럼 정답 범위가 좁을 때 사용한다.
- O/X는 족보형 명제, 자주 뒤집히는 사실, trap에 적합할 때 사용한다.
- MCQ distractor는 가능하면 **같은 강의 안의 실제로 헷갈릴 만한 개념**을 사용한다.
- “다른 mechanism은?”처럼 여러 해석이 가능한 발문은 피하고, “약물–기전 연결이 틀린 것은?”처럼 채점축을 명확히 한다.
- 두 요소 이상을 답해야 한다면 발문에서 요구하는 axis를 명확히 제시한다.
- 독립적인 사실을 3개 이상 한꺼번에 답해야 하는 문제는 기본적으로 분할을 검토한다.
- 단, 하나의 mechanism/sequence 자체가 본질적으로 여러 단계라면 하나의 문제로 유지할 수 있다.
- 쉬운 문제 자체는 나쁜 문제가 아니다. 초기 학습용 atomic recall은 쉽게 만들 수 있다.
- 난이도를 높이기 위해 단서를 없애거나 표현을 모호하게 만들지 마라.
- 고난도 문제는 comparison, reverse retrieval, mechanism, integration에서 만들어라.

## Cloze 작성법

Cloze는 **회수할 핵심이 한 문장 안에 여럿 박혀 있고, 그 문장이 있어야 무엇을 묻는지 서는** 자리에 쓴다. 문장은 그대로 보여 주고 핵심 자리만 비운다. 자료의 문장을 그대로 써도 되고, 문장이 길어도 된다.

**한 카드에 빈칸 하나를 강제하지 마라.** 관련된 빈칸 1–3개가 문장 구조를 드러내면 그쪽이 더 좋다.

```text
Phase I 반응은 -OH, -NH2, -SH 같은 {{c1}}를 {{c2}}한다.
answer_units: [functional group, 도입하거나 노출]
```

빈칸을 어디서 끊느냐가 곧 질문이다. **남는 글자가 질문이고, 가린 글자가 답이다.**

1. **빈칸에는 핵심 개념을 둔다.** 시험에 나올 약물명·표적·기전·효과·수치를 비운다. 조사, 흔한 동사, 문장만 읽어도 채워지는 말은 비우지 않는다. 단계 번호나 기호처럼 실체를 가리키기만 하는 말은 실체와 함께 비운다.
2. **빈칸마다 무엇을 묻는지가 문장에 남아야 한다.**
   - ✗ 반감기는 {{c1}}하고 {{c2}}한다. → 남는 것이 「[ ]하고 [ ]한다」뿐이다
   - ✓ 반감기는 분포용적에 {{c1}}하고 청소율에 {{c2}}한다.
3. **남는 문장이 답을 알려 주면 안 된다.** 가린 말이 문장 다른 자리에 있거나 앞말이 답을 풀어 말하면, 회상이 아니라 읽기가 된다.
   - ✗ Omeprazole은 proton pump 억제제로, 벽세포의 {{c1}}를 비가역적으로 억제한다.
   - ✓ Omeprazole은 벽세포의 {{c1}}를 비가역적으로 억제한다.
4. **답이 되는 덩어리를 통째로 비운다.** 답의 일부가 문장에 남으면 나머지는 짐작된다.
5. **한 문장 안의 빈칸은 같은 축이다.** 축이 다르면 문항을 나눈다.
6. **세거나 나열하는 것은 Cloze가 아니라 List다.** 「~의 세 가지는?」처럼 묶는 이름이 서면 빈칸 문장은 질문과 같은 말이 된다. 문장이 각 항목의 축을 들고 있을 때만 Cloze로 쓴다.

써 놓고 빈칸을 `[ ]`로 바꿔 읽어 본다. **각 `[ ]`가 무엇을 묻는지 말할 수 있고, 답은 떠오르지 않아야 한다.** 둘 중 하나라도 어긋나면 빈칸의 경계를 옮긴다.

# 4. Tier

문제를 다음 세 tier로 나눠라.

## Core
시험 전에 확실히 회수되어야 하는 내용.

주로:
- 교수 강조
- 학습목표
- take-home
- 반복 족보
- 중요한 prerequisite
- 핵심 drug–target / mechanism

## Advanced
Core atomic fact가 어느 정도 회수된 뒤 풀 가치가 있는 문제.

주로:
- reverse
- mechanism
- discrimination
- integration
- sequence
- trap

## Optional
자료에는 있지만 상대적으로 낮은 yield의 세부사항.

Optional이 과도하게 많아지지 않게 해라.

자료에 있다는 이유만으로 모든 세부 내용을 Optional로 보존하려고 하지 마라.

# 5. 각 문제 Metadata

각 문제마다 다음 필드를 반드시 표시해라.

- ID
- Concept ID
- Concept
- Tier
- Importance
- Concept difficulty
- Item difficulty
- Format
- Cognitive type
- Retrieval direction
- Question
- Answer
- Answer units
- Prerequisites
- Source page/slide
- Source strength
- 교수 강조 또는 족보 근거
- Source conflict 여부
- Conflict ID, 해당되는 경우

## Answer units

정답을 self-grade할 수 있도록 핵심 채점 단위를 배열 형태로 분리해라.

예:

Question:
Acyclovir selectivity를 activation 단계와 polymerase 단계로 나누어 설명하라.

Answer units:
- virus가 drug를 phosphorylate
- viral DNA polymerase가 더 sensitive

단순 한 단어 정답이면 answer unit은 하나만 둔다.

## Prerequisites

Mechanism, discrimination, integration, sequence 문제에는 가능하면 그 문제를 풀기 위해 먼저 회수되어야 하는 **atomic question ID**를 prerequisites로 지정해라.

예:

```text
Prerequisites:
- AV-C23
- AV-C25
- AV-C26
```

Direct atomic question은:

```text
Prerequisites: []
```

로 둔다.

Prerequisites는 단순히 같은 concept의 이전 문제를 넣는 것이 아니라, **그 고차원 문제를 풀기 위해 실제로 필요한 기초 retrieval**만 넣어라.

## Source page/slide

근거가 된 자리를 모두 적어라. 강의자료·필기 PDF는 **파일의 실제 쪽 번호**(첫 쪽이 1)를 쓰고, 여러 쪽이면 각각 적어라. 앱이 이 번호로 슬라이드 이미지를 붙인다.

예: `S1 p13; S1 p14` · `S2 2023 11번`

## Source strength

다음 중 적절한 값을 사용해라.

- professor_emphasis
- repeated_past_exam
- recent_past_exam
- lecture_core
- lecture_only
- lecture_low_emphasis
- past_exam_only
- source_conflict

필요하면 복수 값을 허용한다.

예:

```text
Source strength:
- professor_emphasis
- repeated_past_exam
```

# 6. Source Conflict 처리

강의자료와 족보가 서로 다른 표현이나 정답을 제시하면:

1. 외부 지식으로 어느 쪽을 교정하지 마라.
2. 하나의 카드에 섞지 마라.
3. 각각 source-specific question으로 분리해라.
4. 같은 Conflict ID를 부여해라.
5. 각 문항에 어떤 출처 기준인지 발문에 명확히 써라.

예:

```text
Conflict ID: IFN_HOST_NUCLEIC_ACID_01

Question A:
[2026 강의자료 기준] ...

Question B:
[반복 족보 기준] ...
```

자료만으로 정답을 복원할 수 없는 족보 문항은 추정하지 말고 제외하거나 unresolved로 표시해라.

# 7. Quality Audit

최종 출력 전 전체 question bank를 다시 검사해라.

다음을 확인해서 문제가 있으면 스스로 수정해라.

- source grounding
- 발문 명확성
- self-gradeability
- answer burden
- redundancy
- reverse coverage
- discrimination coverage
- integration coverage
- low-yield overproduction
- source conflict preservation
- prerequisite validity
- answer-unit clarity

특히 다음은 수정 대상이다.

- 답이 여러 방향으로 자연스럽게 나올 수 있는 broad question
- 문제를 어렵게 만들기 위해 일부러 모호하게 쓴 발문
- 이미 있는 문제와 거의 같은 retrieval direction
- 중요도 낮은 세부 fact의 과도한 카드화
- 여러 독립 사실을 한꺼번에 요구해 self-grading이 어려운 문제
- prerequisite 없이 너무 높은 단계의 integration 문제
- 자료 근거 없이 생성된 distractor
- source conflict를 하나의 정답으로 합쳐버린 문제

# 8. Final Audit에서 확인할 추가 원칙

High-importance concept에서는 가능한 경우 다음 구조가 자연스럽게 존재하는지 확인해라.

```text
atomic direct
→ reverse 또는 discrimination
→ mechanism
→ integration
```

단, 모든 concept에 이 구조를 강제로 적용하지 마라.

중요도가 낮은 concept은 direct 1문항으로 충분할 수 있다.

또한 전체 bank가 다음 방향으로 치우치지 않았는지 확인해라.

- direct recall만 지나치게 많음
- reverse가 거의 없음
- integration이 과도함
- O/X가 과도함
- broad list recall이 많음
- low-yield 세부사항이 Core를 잠식함


# 이번 강의

- 강의: {{title}}
- 시험일: {{exam_date}}
- 자료 중요도 비중: **{{weighting}}**
- 첨부 자료:
{{sources}}

자료 중요도 비중은 **중요도 판단 비중**이다. 정답의 권위나 충돌 해결 우선순위로 사용하지 마라.

`sequence`는 retrieval direction과 문제 형식 양쪽에서 쓸 수 있다. 두 필드는 독립적으로 기록하고, 한쪽이 sequence라고 다른 쪽도 자동 지정하지 마라.

# 9. 출력 형식

{{output}} 아래 순서와 이름을 그대로 써라. 이름이 같아야 앱이 읽는다.

## 1. Concept Map

표. 열은 이 순서:

`concept_id | title | core_facts | importance | importance_rationale | concept_difficulty | tier | exam_signal_strength | related_concepts | source_refs`

- tier: Core / Advanced / Optional 중 하나
- exam_signal_strength: low / medium / high
- core_facts·related_concepts는 `;`로 구분

## 2. Retrieval Plan

표. 열은 이 순서:

`concept_id | directions | rationale | repetition_budget | target_mastery`

- repetition_budget: 1–100. 시험까지 이 concept에 줄 반복량
- target_mastery: 0.1–1. 시험 전 도달할 숙련도

## 3. Question Bank

Core → Advanced → Optional 순서. 문제마다 아래 블록 하나.

```text
### Q001
- question_id:
- concept_id:
- tier:
- importance:
- concept_difficulty:
- item_difficulty:          1–5
- format:                   basic / cloze / list / ox / mcq / multi_select / matching / sequence
- cognitive_type:           direct / reverse / mechanism / discrimination / integration / sequence / trap
- retrieval_direction:      위와 같은 일곱 값
- question:
- answer:
- answer_units:             [ ... ]
- prerequisites:            [ ... ]
- source_refs:
- source_strength:
- exam_rationale:           교수 강조 또는 족보 근거
- conflict_id:              없으면 비워 둔다
```

형식별로 이 줄을 더한다.

- **cloze**: question에 빈칸을 `{{c1}}`, `{{c2}}`, `{{c3}}`로만 표시하고, 답은 answer_units에 순서대로 둔다.
- **ox**: answer는 `O` 또는 `X`. 설명은 answer_units에 둔다.
- **mcq / multi_select**: `options: [A: ..., B: ...]` 와 `correct_option_ids: [ ... ]`
- **matching**: `matching_left: [ ... ]` · `matching_right: [ ... ]` · `answer_pairs: [왼쪽-오른쪽, ...]`
- **sequence**: `sequence_items: [A: ..., B: ...]` · `correct_order: [ ... ]`

## 4. Source Conflicts

표. 열은 이 순서:

`conflict_id | description | source_refs | unresolved`

## 5. 자료 요약

첨부 자료마다 한 줄: `source_id | 무엇이 들어 있는지`

## 6. Quality Audit

다음 항목별로 실제로 무엇을 수정했는지 짧게 보고한다.

- clarity
- gradeability
- answer burden
- redundancy
- reverse coverage
- discrimination
- integration
- low-yield
- source conflicts
- prerequisites

걸러 낸 후보 문제 수와 남은 경고도 적는다.

## 7. Final Statistics

- 총 문제 수
- Core 수
- Advanced 수
- Optional 수
- Format별 문제 수
- Cognitive type별 문제 수
- Importance 5 문제 수
- Source conflict 문제 수

그리고 가장 높은 학습 우선순위 concept 5–10개를 따로 요약해라.

마지막 줄에 `STUDYEZ_BANK_COMPLETE`를 적어라. 응답이 끝나지 않았으면 적지 마라.
