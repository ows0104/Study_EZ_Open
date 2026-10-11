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
    voice.md             문제·힌트의 상황 중심 말투 (일반·간소화 생성, 검수·수선 공용)

`philosophy.md`는 예전 단일 프롬프트에서 모듈로 옮겼다는 안내이며 실행 규칙의 정본이 아니다.

## 새 규칙을 둘 곳

Quiz Bank의 별도 출제 정본은 `web/src/bank/bankPrompt.md` v2.0이다.
v4 JSON 계약은 `server/app/bank_validation/schema.py`와 `learning.py`에서 검증한다.
`coverage_inventory`는 자료 범위를 target/explanation/excluded/uncertain으로 분류하며,
`learning_objectives`는 회독·복습을 집계하는 단위다. 각 문항은 주 요점 하나와
learning/variant/exam 역할, 선택적 `recall_prompt`, 객관식 선지별 해설을 가진다.
문항 제거로 학습요점이 사라지지 않으며, 학습 문항이 없는 요점은 설명 학습과 결손 표시로 남는다.
옛 응답에 없는 학습요점을 정리 단계가 추측하여 생성하지 않는다.
시험 제외가 명시된 강의는 근거·출처가 있는 범위 목록을 보존한 v4 빈 은행으로 검증할 수 있다.
빈 목록이나 학습 대상 요점이 누락된 은행은 허용하지 않으며, 범위 제외는 학습 완료로 집계하지 않는다.
시험용 통합 문항은 주 요점과 보조 요점을 모두 처음 학습한 뒤에만 출제한다.

일일 계획은 모든 강의의 공통 시간 예산을 사용한다. 기본 배분은 새 범위 50%,
복습 25%, 단순 암기 12.5%, 누적 확인 12.5%이며 목표일까지 새 범위가 많으면
새 범위를 80%까지 늘린다. 사용하지 못한 배분은 다른 활동에 넘긴다.
계획은 날짜별로 고정하며 사용자가 남은 계획을 조정할 때만 다시 계산한다.
복습 간격 1일 시작·확실한 지연 회상 시 두 배(최대 90일)는 초기 휴리스틱이다.
보조 설명, 찍음, 자기평가와 실제 객관식 채점은 구분하고, 같은 날 반복을
지연 회상 성공으로 세지 않는다. 점수 예측이나 검증된 망각 확률을 뜻하지 않는다.

- 분야와 학습 목적에 공통인 판단만 Core에 둔다.
- 목적에 따른 판단은 Profile, 입력 유무에 따른 것은 Adapter에 둔다.
- 용어·분야별 예시는 Domain에 둔다.
- 구조적으로 검증 가능한 조건은 스키마·검증 코드와 함께 바꾼다.
- 실패 이력은 실행 프롬프트에 넣지 않고 [기록](archive/quizgen-cases.md)으로 연결한다.

프롬프트 예시의 강의·동일 주제는 평가 표본에서 제외한다.
예시 출처는 `prompting.py`의 `DOMAINS` 주석을 확인한다.
