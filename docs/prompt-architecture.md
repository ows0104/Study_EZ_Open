# 프롬프트 조립 구조

실행 지침은 작은 모듈을 합쳐 만든다. 조립 순서의 정본은
[quizgen/prompting.py](../quizgen/prompting.py)다.
실제 프롬프트는 실행 입력이므로 문서 정리와 구분해 변경한다.

## 조립 순서와 파일

경로는 `quizgen/prompts/` 기준이다.

| 순서 | 역할 | 파일 |
|---|---|---|
| 1. Core | 공통 카드 품질 | `core/quality.md` |
| | 근거·미디어·말투 | `core/evidence.md`, `core/media.md`, `core/language.md` |
| 2. Profile | 복습 또는 예습 목적 | `profiles/exam_review.md`, `profiles/prelecture.md` |
| 3. Adapters | 필기 PDF·주석 | `adapters/lecture_pdf.md`, `adapters/annotations.md` |
| | 기출 자료가 있을 때 | `adapters/past_exam.md` |
| | 의학 기출 보정·채점 | `adapters/medical_past_exam.md`, `adapters/medical_past_exam_grade.md` |
| 4. Domain | 용어·도메인 규약 | `domains/medical_ko.md`, `domains/generic.md` |

복습은 `exam_review`, 예습은 `prelecture`를 선택한다.
기본 도메인은 `medical_ko`, `--domain generic`도 지원한다.
의학 기출 보정은 도메인·출처·호출 단계의 조건을 함께 따른다.

## 단계별 과제

공통 모듈 뒤에 단계 지시와 입력·출력 계약이 붙는다.
다음은 `quizgen/prompts/`에서 직접 읽는 파일이다.

    plan.md              무엇을 낼지 계획
    cards.md             카드 생성
    revise.md            수정 슬라이드의 카드 갱신
    reproduce_answer.md  답을 보지 않고 다시 풀기
    reproduce_grade.md   원래 답과 비교
    reproduce_axis.md    cloze 빈칸의 질문 축 확인
    repair.md            검사에 걸린 카드 수선
    repair_leak.md       앞면 누출 수선
    judge_cloze.md       두 시도에 대한 가림 평가

예습 단계는 `quizgen/prequiz/prompts/`의 파일을 사용한다.

    must.md              꼭 알아야 할 항목 선택
    cards.md             예습 카드 생성
    repair.md            예습 카드 수선

`philosophy.md`는 예전 단일 프롬프트에서 모듈로 옮겼다는 안내이며 실행 규칙의 정본이 아니다.

## 새 규칙을 둘 곳

Quiz Bank 출제 정본은 `web/src/bank/bankPrompt.md` 1.47다. 웹은 원본 전체로 문항부터 작성하며,
Exam Point Plan·Concept Map·Retrieval Plan과 concept_id·prerequisites는 웹 출력에서 제외한다.
웹은 객관식의 고정 선지 한 세트를 완성한다. 1.43 이상은 `option_pools.py`가 정리 뒤 실제
변형 가치가 있는 문항에만 보기 풀을 선택적으로 작성하고 모든 후보를 이후 내용 검수에 포함한다.
CLI는 원본만 읽는 별도 작업 폴더에서 출제포인트를 독립 추출한다. `web_audit.py`·`repair.py`가
원본·독립 목록·실제 문항과 필요한 회상 방향을 대조·보완하고, 내용 검수 뒤 `question_first.py`와
`prompts/learning-structure.md`가 최종 문항에 개념도·회상 계획·선행 관계만 연결한다.
웹 출제 버튼은 `points` 준비 작업을 함께 요청해 웹 응답 대기 중 원본 독립 추출을 진행한다.
`quizbank.independent`는 같은 PDF·족보·강의 범위의 완료 포인트를 재사용하며, 본 처리는
`--points-cache-root`로 미리 저장된 목록을 찾아 사용한다. 원본 준비 API는 문항·웹 응답을 전달하지 않는다.
목록이나 개념도는 출제 범위의 상한이 아니다. 학습 구조 연결 시 문항 내용을 보존하고 실행 가능한 구조를 검증한다.
CLI는 각 단계의 과제·자료·처리 순서·출력 계약을 먼저 전달한 뒤 정본의 「문항 품질 원칙」을 붙인다.
정리기는 응답 보존·JSON 변환만, 독립 의학 검토는 정답의 정확성만 맡는다. 공통 출제 원칙의 사본을
각 프롬프트에 만들지 않는다. 원본 대조는 개념 등장과 방향별 실제 시험을 분리하고 필수 누락·확장
제안을 구분한다. 수정은 기존 문항 보완을 우선하며 추가에는 독립 목표와 기존 문항 수정으로 해결하기
어려운 이유를 기록한다. 출제포인트 수와 문항 수를 일대일로 맞추지 않는다.
최종 검수 지적은 보존하며 내용 오류·누락이 남아도 게시한다. 학습 구조·ID 등 실행 가능한 구조 검증은 게시 여부와 별도로 확인한다. 1.41 이하의 계획 선행 응답은 기존 처리 경로를 유지한다.
V1 문항별 학습을 사용하며
JSON 3.1에는 선택적인 `option_explanations`·`option_pools`를 보존한다. 기존 3.0 은행은 그대로 읽는다.
`quality.py`는 새 은행의 문자 그대로 정답 노출을 검사한다. 조건과 원문 범위 누락은 출제 시 원본 대조로 확인한다.
`choices.py`는 동일 내용에 묶인 의학 검토가 통과한 후보만 사용하며, 제시한 보기·정답·해설은 함께 고정한다.
보기 변형은 새 학습 분량을 만들지 않고 복습 간격은 기존 V1 `policy.json`으로 계산한다.


- 분야와 학습 목적에 공통인 판단만 Core에 둔다.
- 목적에 따른 판단은 Profile, 입력 유무에 따른 것은 Adapter에 둔다.
- 용어·분야별 예시는 Domain에 둔다.
- 구조적으로 검증 가능한 조건은 스키마·검증 코드와 함께 바꾼다.
- 실패 이력은 실행 프롬프트에 넣지 않고 [기록](archive/quizgen-cases.md)으로 연결한다.

프롬프트 예시의 강의·동일 주제는 평가 표본에서 제외한다.
예시 출처는 `prompting.py`의 `DOMAINS` 주석을 확인한다.
