<!--
Bank Builder 프롬프트 — 정본
Version: 1.13

이 파일이 ChatGPT에 가는 프롬프트의 정본이다. 이 주석은 보내지 않는다.
{{…}} 자리는 web/src/bank/prompt.ts 가 강의마다 채운다. {{c1}} 같은 cloze 표기는 그대로 간다.
고치면 아래에 판을 하나 올리고 Version 을 같이 올린다. 서버에 응답이 저장될 때 이 Version 이 같이 남는다.

1.13 (2026-10-07) Core 서술은 짧은 용어·관계·채점 항목으로 회수하게 한다. 긴 문장 재현을 요구하지 않고,
                   answer와 answer_units를 같은 최소 정답 단위로 쓴다. 넓은 설명은 회수 축을 나눈다.

1.12 (2026-10-06) Optional 문항 수를 억제하는 지시를 뺀다. 학습 가치가 있는 세부사항은 보존하고,
                   낮은 중요도는 tier·importance에 반영해 앱에서 노출과 학습률 비중을 조절한다.

1.11 (2026-10-06) Question Bank를 공통 표와 형식별 상세 표로 출력한다. 필드 이름의 반복을 줄이되
                   문항·채점 단위·메타데이터는 보존한다. 배열은 셀 안에서 <br>로 구분한다.

1.10 (2026-10-06) Phase I 예시의 작용기도 빈칸으로 바꾼다. Cloze의 answer는 각 빈칸을 채우고
                   정답 부분을 굵게 강조한 전체 문장으로 쓴다.

1.9 (2026-10-06)  한 문항의 빈칸은 모두 c1로 묶고, 답은 빈칸 등장 순서대로 대응한다.
                   Omeprazole 예시에서 작용 세포와 표적을 함께 비운다. 점검 결과의 별도 보고를 금지하는 문장을 뺐다.

1.8 (2026-10-06)  개념 그래프에 표시할 짧은 요약 이름 graph_title을 전체 title과 별도로 만든다.

1.7 (2026-10-06)  발문에서 「강의에서 제시한」·「2016-2 족보에서」 같은 출처 수식어를 빼고 개념 자체를 묻는다.
                   출처는 메타데이터에 남기며, 답을 한정하는 데 필요한 조건·분류 기준은 발문에 명시한다.

1.6 (2026-10-05)  앱이 읽지 않는 칸을 뺐다(관리자): 문항마다 적던 concept_difficulty(개념 표에 이미 있다) ·
                   cognitive_type(retrieval_direction 과 거의 같고 앱은 그쪽만 쓴다) · source_strength, 그리고
                   Retrieval Plan 의 rationale. 자료 밖 표시는 `EXT` 하나로 한다. §5 필드 목록을 §9 출력 형식과
                   맞췄다(§5 에만 있던 「Concept」·「Source conflict 여부」가 두 지시를 어긋나게 했다).

1.5 (2026-10-05)  출력 끝의 「자료 요약」과 「Quality Audit」 보고를 뺐다(관리자). 앱이 읽지 않는다 — 검증기가 있는지만
                   봤다. 점검(§7)은 그대로 시키고 결과만 낸다. Final Statistics 는 중요한 값만 남겼다(관리자 —
                   「최종 통계도 중요한 값만 뽑기는 하자」): 총 문제 수 · tier별 · 충돌 · 외부 의학지식.

1.4 (2026-10-05)  §7 Final Statistics 끝의 「가장 높은 학습 우선순위 concept 5–10개를 따로 요약해라」를 뺐다(관리자).
                   앱이 읽지 않는 출력이다 — 우선순위는 개념 지도가 중요도·진척으로 보여 준다.

1.3 (2026-10-05)  짝짓기 왼쪽에 1. 2. 3., 오른쪽에 A. B. C. 를 붙이고 정답 짝을 `1. 왼쪽 - A. 오른쪽` 으로 적는다
                   (관리자 제안 — 「컴퓨터, 인간 모두 읽을 수 있게」). 261002_03 Q046 이 정답 짝에 보기 글을 줄여 써서
                   짝을 못 찾고 빠졌다. 이제 정리가 꼬리표로 찾는다(quizbank/organize.py `_resolve`).

1.2 (2026-10-05)  관리자 지시 — 「외부 의학지식을 충분히 이용해도 되는데, 자료에 없거나 다른 경우에 표시만
                   해 주면 돼. 강의록·족보가 충돌할 때는 외부 의학지식이 필요하겠지. 충돌이 있는 문제들은 합치고
                   표시만 해줘.」 머리의 「외부 의학지식은 사용하지 말고…」를 걷었다. 자료 밖 내용은 출처 `EXT` 와
                   source strength `external_knowledge` 로 표시한다. §6 충돌은 출처별로 가르지 않고 **한 문항으로
                   합쳐** 외부 의학지식으로 정답을 정하고, 충돌 표에 무엇이 어떻게 다른지와 고른 근거를 적는다.
                   첫 실물 261002_03(v1.1)에서 갈라 낸 두 문항 중 족보 쪽(Q009)을 외부지식 검토가 wrong 으로 잡았다
                   — 갈라 두면 틀린 답을 그대로 가르치는 문항이 하나 생긴다.

1.1 이사 (2026-10-04)  AdaptiveStudy3/bank_builder/bank_prompt.md 에서 이리로 옮겼다 — 사이트에서
                   만들게 되면서. 내용은 그대로다. 그쪽 파일은 「이사했다」만 남긴다.

1.1 (2026-10-04)  v1.0(저장소 루트 Bankbuilder_v1.0.md, 기록으로 둔다)의 §1–8을 옮겨 왔다.
                   §3에 「Cloze 작성법」 — 빈칸 여럿 허용, 핵심 개념을 비운다, 축은 남기고 답은 남기지 않는다,
                   나열은 List로. quizgen/prompts/core/quality.md의 cloze 규칙에서 골랐다.
                   §5에 「Source page/slide」 — PDF 실제 쪽 번호, 여러 쪽이면 각각(슬라이드 이미지를 붙이려고).
                   §9를 앱이 읽는 열·필드 이름으로 고정하고, 강의 설정 칸을 넣었다.
-->
첨부한 **올해 필기/강의자료와 족보**를 중심으로 의대 시험 대비용 question bank를 만들어줘.

외부 의학지식은 충분히 써도 된다. 단 **자료에 없거나 자료와 다른 내용**을 문항에 쓰면 그 문항에 표시해라(§5 Source page/slide의 `EXT`).

강의자료와 족보가 서로 충돌하면 외부 의학지식으로 맞는 답을 정해 **한 문항으로 합치고, source conflict로 표시**해라(§6).

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

학습 가치가 있는 낮은 중요도의 내용도 문제은행에 보존하고, Optional과 해당 중요도로 표시해라.

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
- 발문은 **출처가 아니라 개념 자체**를 묻는다. 「강의에서 제시한」, 「자료에 따르면」, 「2016-2 족보에서」 같은 출처 수식어는 쓰지 않는다. 출처·출제 연도는 `source_refs`·`exam_rationale`에 기록한다. 출처 수식어를 빼면 답의 범위가 모호해지는 경우, 필요한 조건·분류 기준·단계의 범위를 발문에 직접 명시한다.
  - ✗ 강의에서 제시한 약리학적 사고의 전체 흐름을 순서대로 배열하라. → ✓ 약리학적 사고의 전체 흐름을 순서대로 배열하라.
  - ✗ 2016-2 족보에서 simvastatin은 기원·제조 방식에 따라 어떤 약물로 분류되었는가? → ✓ Simvastatin은 기원·제조 방식에 따라 어떤 약물로 분류되는가?
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

한 문항의 빈칸은 함께 회수하도록 **모두 `{{c1}}`로 표시**한다. `answer_units`에는 빈칸이 등장하는 순서대로 답을 하나씩 적는다. 같은 `c1`이어도 답이 같다는 뜻은 아니다. Anki로 옮길 때는 각 자리에 대응하는 답을 넣어 `{{c1::정답}}`으로 변환하면 한 카드에서 함께 가려진다.

```text
Phase I 반응은 {{c1}} 같은 {{c1}}를 {{c1}}한다.
answer_units: [(-OH, -NH2, -SH), functional group, 도입하거나 노출]
answer: Phase I 반응은 **(-OH, -NH2, -SH)** 같은 **functional group**를 **도입하거나 노출**한다.
```

빈칸을 어디서 끊느냐가 곧 질문이다. **남는 글자가 질문이고, 가린 글자가 답이다.**

1. **빈칸에는 핵심 개념을 둔다.** 시험에 나올 약물명·표적·기전·효과·수치를 비운다. 조사, 흔한 동사, 문장만 읽어도 채워지는 말은 비우지 않는다. 단계 번호나 기호처럼 실체를 가리키기만 하는 말은 실체와 함께 비운다.
2. **빈칸마다 무엇을 묻는지가 문장에 남아야 한다.**
   - ✗ 반감기는 {{c1}}하고 {{c1}}한다. → 남는 것이 「[ ]하고 [ ]한다」뿐이다
   - ✓ 반감기는 분포용적에 {{c1}}하고 청소율에 {{c1}}한다.
3. **남는 문장이 답을 알려 주면 안 된다.** 가린 말이 문장 다른 자리에 있거나 앞말이 답을 풀어 말하면, 회상이 아니라 읽기가 된다.
   - ✗ Omeprazole은 proton pump 억제제로, 벽세포의 {{c1}}를 비가역적으로 억제한다.
   - ✓ Omeprazole은 {{c1}}의 {{c1}}를 비가역적으로 억제한다.
     `answer_units: [벽세포, H+/K+-ATPase]`
4. **답이 되는 덩어리를 통째로 비운다.** 답의 일부가 문장에 남으면 나머지는 짐작된다.
5. **한 문장 안의 빈칸은 같은 축이다.** 축이 다르면 문항을 나눈다.
6. **세거나 나열하는 것은 Cloze가 아니라 List다.** 「~의 세 가지는?」처럼 묶는 이름이 서면 빈칸 문장은 질문과 같은 말이 된다. 문장이 각 항목의 축을 들고 있을 때만 Cloze로 쓴다.

써 놓고 빈칸을 `[ ]`로 바꿔 읽어 본다. **각 `[ ]`가 무엇을 묻는지 말할 수 있고, 답은 떠오르지 않아야 한다.** 둘 중 하나라도 어긋나면 빈칸의 경계를 옮긴다.

# 4. Tier

문제를 다음 세 tier로 나눠라.

## Core
시험 전에 확실히 회수되어야 하는 내용.

**짧게 회상하고 항목별로 바로 채점할 수 있게 만든다.** Core는 긴 서술문을 재현하는 형식으로 만들지 마라.
- 한 용어·한 관계·한 판단을 묻는 atomic recall을 기본으로 한다. 서로 짝을 이루는 두 관계는 함께 물어도 된다.
- Basic의 답은 용어, `A → B`, 짧은 원인–결과처럼 최소 정답으로 쓴다. 여러 항목이면 항목별로 분리하고, 이를 하나의 긴 문장으로 다시 합치지 마라.
- 발문은 무엇을 몇 개 답해야 하는지 명확히 한다. 「전체를 설명하라」처럼 회수 범위가 넓으면 축별로 나누거나 List·Matching·Cloze로 바꾼다.
- 기전이 중요해서 Core인 경우에도 핵심 표적·작용·결과를 짧은 관계로 묻는다. 여러 독립 사실을 한꺼번에 요구하는 부담은 문항을 나누어 줄인다.
- 문장 표현·조사·연결어를 기억할 필요 없이 핵심 항목을 맞히면 정답이어야 한다.

예:
```text
question: 시간에 따른 약물 효과를 예측하려면 어떤 두 관계를 함께 알아야 하는가?
format: basic
answer: 약동학: 시간 → 농도<br>약력학: 농도 → 반응
answer_units: 약동학: 시간 → 농도<br>약력학: 농도 → 반응
```
「시간에 따른 약물 농도 변화인 약동학과 농도에 따른 반응인 약력학을 함께 알아야 한다」처럼 긴 문장으로 바꾸지 마라.

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

Optional이라는 이유로 문항 수나 비율을 줄이지 마라. 학습 가치가 있는 세부사항은 문제은행에 보존해라.
개념과 문항의 tier·importance는 실제 중요도에 맞게 표시해라.
낮은 중요도의 문항을 덜 보여주고 전체 학습률에 적게 반영하는 것은 앱의 학습 정책에서 처리한다.

# 5. 각 문제 Metadata

각 문제마다 다음 필드를 반드시 표시해라.

- ID
- Concept ID
- Tier
- Importance
- Item difficulty
- Format
- Retrieval direction
- Question
- Answer
- Answer units
- Prerequisites
- Source page/slide
- 교수 강조 또는 족보 근거
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

Core Basic은 `answer`와 `answer_units`를 같은 짧은 정답 항목으로 쓴다. 부연설명이나 별도의 회수 내용을 채점 항목에 끼워 넣지 마라.

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

자료에 없는 내용을 외부 의학지식으로 쓴 문항은 `EXT 외부 의학지식`을 같이 적어라(자료 쪽 근거가 있으면 그것도 함께).

# 6. Source Conflict 처리

강의자료와 족보(또는 자료 안의 두 자리)가 서로 다른 표현이나 정답을 제시하면:

1. 출처별로 문항을 나누지 말고 **한 문항으로 합쳐라.**
2. 정답은 외부 의학지식으로 맞는 쪽을 정해라. 둘 다 맞는 표현이면 그렇게 답하고, 둘 다 틀렸으면 맞는 답을 써라.
3. 그 문항에 Conflict ID를 붙이고, Source page/slide에 충돌한 자리를 모두 적어라. 외부 의학지식으로 정했으면 `EXT`도 함께 적는다.
4. Source Conflicts 표의 description에 **각 출처가 무엇이라고 하는지, 문항의 정답이 무엇이고 왜 그쪽인지**를 적어라. 학생이 답을 본 뒤 이 설명을 읽는다.

예:

```text
Conflict ID: ALPHA2_TRANSMITTER_01
Question: Presynaptic α2 수용체를 차단하면 교감신경 말단에서 유리가 증가하는 전달물질은?
Answer: norepinephrine
Source page/slide: S1 p22; S2 2023 18번; EXT 외부 의학지식

description: 강의자료(S1 p22)는 α2 활성화가 norepinephrine 유리를 억제한다고 쓰고, 2023 족보 18번 정답은
「α2 억제 시 epinephrine 증가」다. 교감신경 말단의 전달물질은 norepinephrine이라 문항은 강의자료 쪽으로 답한다.
```

자료만으로 정답을 복원할 수 없는 족보 문항(정답 미확인 등)은 외부 의학지식으로 정답을 정하고 `EXT`로 표시해라. 외부 지식으로도 정할 수 없으면 제외해라.

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
- source conflict 표시 (합친 문항 · 설명)
- prerequisite validity
- answer-unit clarity

특히 다음은 수정 대상이다.

- 답이 여러 방향으로 자연스럽게 나올 수 있는 broad question
- 문제를 어렵게 만들기 위해 일부러 모호하게 쓴 발문
- 「강의에서 제시한」·「족보에서」 등 출처 수식어로 개념 질문을 대신하거나 답의 범위를 한정한 발문
- 이미 있는 문제와 거의 같은 retrieval direction
- 중요도 낮은 세부 fact의 과도한 카드화
- 여러 독립 사실을 한꺼번에 요구해 self-grading이 어려운 문제
- prerequisite 없이 너무 높은 단계의 integration 문제
- 자료 근거 없이 생성된 distractor
- 충돌을 합치면서 어느 쪽이 왜 맞는지 설명하지 않은 문제
- 자료에 없는 내용을 썼는데 `EXT` 표시가 없는 문제

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

자료 중요도 비중은 **중요도 판단 비중**이다. 충돌 해결 우선순위로 사용하지 마라 — 충돌은 외부 의학지식으로 판단한다(§6).

`sequence`는 retrieval direction과 문제 형식 양쪽에서 쓸 수 있다. 두 필드는 독립적으로 기록하고, 한쪽이 sequence라고 다른 쪽도 자동 지정하지 마라.

# 9. 출력 형식

{{output}} 아래 순서와 이름을 그대로 써라. 이름이 같아야 앱이 읽는다.

## 1. Concept Map

표. 열은 이 순서:

`concept_id | title | graph_title | core_facts | importance | importance_rationale | concept_difficulty | tier | exam_signal_strength | related_concepts | source_refs`

- tier: Core / Advanced / Optional 중 하나
- exam_signal_strength: low / medium / high
- core_facts·related_concepts는 `;`로 구분
- graph_title: 그래프에서 한눈에 알아볼 짧은 이름. title의 핵심 명사 2–3개를 한글 기준 8–14자 정도로 요약하고 줄임표는 쓰지 마라. 약물명·수용체명·비교 대상·긍정/부정 등 개념을 구분하는 정보는 남겨라. 임의의 약어는 만들지 말고 필요하면 권장 길이를 넘어도 된다. 같은 은행에서 이름만 보고 개념을 구분할 수 있어야 한다. 예: `심혈관 M2 기전과 차단 효과` → `M2 기전과 차단`. 전체 title과 core_facts는 그대로 상세하게 쓴다.

## 2. Retrieval Plan

표. 열은 이 순서:

`concept_id | directions | repetition_budget | target_mastery`

- repetition_budget: 1–100. 시험까지 이 concept에 줄 반복량
- target_mastery: 0.1–1. 시험 전 도달할 숙련도

## 3. Question Bank

문항별 필드 블록 대신 아래 마크다운 표로 출력한다. 내용을 줄이지 말고 필드 이름의 반복만 줄여라.

### 3.1 Questions

Core → Advanced → Optional 순서로 **문항당 한 행**. 모든 문항을 이 표에 넣는다. 열은 이 순서:

`question_id | concept_id | tier | importance | item_difficulty | format | retrieval_direction | question | answer | answer_units | prerequisites | source_refs | exam_rationale | conflict_id`

- question_id는 은행 전체에서 유일하며 상세 표와 prerequisites에서도 같은 ID를 쓴다.
- importance·item_difficulty: 1–5. concept의 값으로 자동 대체하지 말고 문항별로 평가한다.
- format: basic / cloze / list / ox / mcq / multi_select / matching / sequence
- retrieval_direction: direct / reverse / mechanism / discrimination / integration / sequence / trap. `matching`은 형식이며 회수 방향이 아니다.
- answer_units·prerequisites는 항목 사이를 `<br>`로 구분한다. 대괄호로 감싸지 않는다. 쉼표·세미콜론은 항목 내부에도 쓰이므로 배열 구분자로 쓰지 않는다.
- prerequisites가 없으면 `—`, conflict_id가 없으면 `—`. 그 외 필수 값은 생략하지 않는다.
- source_refs는 기존처럼 `S1 p13; S1 p14; EXT 외부 의학지식`으로 쓴다. exam_rationale에는 해당 문항의 교수 강조 또는 족보 근거를 남긴다.
- **cloze**: question의 빈칸 1–3개를 모두 `{{c1}}`로 표시한다. answer_units는 빈칸 등장 순서대로 하나씩 두고, question에는 답을 넣지 않는다. answer에는 정답을 채운 전체 문장을 쓰고 채운 정답 부분만 `**굵게**` 강조한다.
- **ox**: answer는 `O` 또는 `X`. 설명은 answer_units에 둔다.
- **Core basic**: answer는 짧은 정답 항목만 쓴다. 여러 항목이면 `<br>`로 구분하고 answer_units에도 같은 항목을 같은 순서로 적는다. 긴 서술문으로 다시 합치지 않는다.

### 3.2 Choice Details

mcq / multi_select 문항만 한 행씩. 해당 문항이 없으면 이 절을 생략한다.

`question_id | options | correct_option_ids`

- options: `A: 선택지<br>B: 선택지`처럼 각 선택지를 구분한다.
- correct_option_ids: `A` 또는 `A<br>C`처럼 정답 ID만 적는다.

### 3.3 Matching Details

matching 문항만 한 행씩. 해당 문항이 없으면 이 절을 생략한다.

`question_id | matching_left | matching_right | answer_pairs`

- matching_left: `1. 항목<br>2. 항목`, matching_right: `A. 항목<br>B. 항목`.
- answer_pairs: `1. 왼쪽 - B. 오른쪽<br>2. 왼쪽 - A. 오른쪽`처럼 번호와 글을 함께 쓴다.

### 3.4 Sequence Details

sequence 문항만 한 행씩. 해당 문항이 없으면 이 절을 생략한다.

`question_id | sequence_items | correct_order`

- sequence_items: `A: 항목<br>B: 항목`, correct_order: `B<br>A`처럼 순서대로 ID를 적는다.

Question Bank 표 공통 규칙:

- 한 행을 실제 줄바꿈으로 나누지 않는다. 문장 안의 줄바꿈도 `<br>`로 표시한다. 배열 필드에서는 `<br>` 하나가 항목 경계이므로 항목 내부의 줄바꿈은 공백으로 바꾼다.
- 셀 본문에 필요한 `|`는 `&#124;`로 쓴다. 셀 경계의 `|`와 구분한다.
- 셀 폭을 맞추는 공백, 문항별 제목·필드 목록, 같은 문항의 재출력은 넣지 않는다. 긴 문장·정답·출처를 줄임표로 줄이지 마라.
- 상세 표는 Questions의 해당 문항과 question_id로 연결한다. 필요한 상세 행을 빠뜨리거나 같은 ID를 두 번 넣지 마라.

## 4. Source Conflicts

표. 열은 이 순서:

`conflict_id | description | source_refs | unresolved`

- description: 각 출처의 말 · 문항의 정답 · 그쪽인 근거(§6)
- unresolved: 외부 의학지식으로도 어느 쪽인지 정하지 못했으면 true

## 5. Final Statistics

- 총 문제 수
- Core · Advanced · Optional 수
- Source conflict 문제 수
- 외부 의학지식(`EXT`)을 쓴 문제 수


마지막 줄에 `STUDYEZ_BANK_COMPLETE`를 적어라. 응답이 끝나지 않았으면 적지 마라.
