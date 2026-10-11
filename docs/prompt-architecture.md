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

Quiz Bank의 별도 출제 정본은 `web/src/bank/bankPrompt.md` v2.2이다.
v4.1 JSON 계약은 `server/app/bank_validation/schema.py`·`learning.py`·`quality.py`에서 검증한다.
`coverage_inventory`는 자료 범위를 target/explanation/excluded/uncertain으로 분류하며,
`learning_objectives`는 회독·복습을 집계하는 단위다. 각 문항은 주 요점 하나와
learning/variant/exam 역할, 선택적 `recall_prompt`, 객관식 선지별 해설을 가진다.
문항 제거로 학습요점이 사라지지 않으며, 학습 문항이 없는 요점은 설명 학습과 결손 표시로 남는다.
옛 응답에 없는 학습요점을 정리 단계가 추측하여 생성하지 않는다.
시험 제외가 명시된 강의는 근거·출처가 있는 범위 목록을 보존한 v4 빈 은행으로 검증할 수 있다.
빈 목록이나 학습 대상 요점이 누락된 은행은 허용하지 않으며, 범위 제외는 학습 완료로 집계하지 않는다.
시험용 통합 문항은 주 요점과 보조 요점을 모두 처음 학습한 뒤에만 출제한다.

v4.1은 요점마다 완전한 대표 learning 문항 하나를 요구한다. 독립 사실을 한 요점에 묶어
대표 하나만 보고 회독 처리하지 않도록 출제 단계에서 분리한다. 비교·구별 요점의 대표는
객관식이며, 단순 사실을 억지로 객관식으로 늘리거나 일률적인 객관식 비율을 강제하지 않는다.
시험용 객관식만 있고 평소 대표 객관식이 없는 새 은행은 통과하지 않는다.
`exam_design`은 시험 문항별 비교 기출 위치·바꾼 판단 축·새로움 설명을 보존한다.
이 설명은 출제자의 주장이다. 의미상 기출 재탕 여부는 원본과 별도 대조해야 한다.
정답을 발문에 모두 노출한 비선택형 문항은 오류, 일부 노출은 검토 경고로 처리한다.
러너는 출제 프롬프트 버전을 정리 단계에 전달한다. v2.1 이후 응답은 표 누락으로
v4.0 검증으로 내려갈 수 없다. 기존 v3/v4.0 은행의 계약은 유지한다.

일일 계획은 모든 강의의 공통 시간 예산을 사용한다. 기본 배분은 새 범위 50%,
복습 25%, 단순 암기 12.5%, 누적 확인 12.5%이며 목표일까지 새 범위가 많으면
새 범위를 80%까지 늘린다. 사용하지 못한 배분은 다른 활동에 넘긴다.
계획은 날짜별로 고정하며 사용자가 남은 계획을 조정할 때만 다시 계산한다.
정답 전 확신은 선택 사항이며, 정답 후 실제 회상을 Again·Hard·Good·Easy로 평가한다.
어렵게 스스로 맞힌 답은 Hard로 성공을 인정한다. 오답·찍음·도움 받은 답은 Again이고,
설명만 읽은 노출은 회상 평가로 넣지 않는다. 기존 클라이언트는 정오답·확신에서 평가를 추정한다.
복습 간격은 `learning_srs.py`의 FSRS 기본 매개변수와 목표 유지율 0.9로 계산한다.
요점별 하루 한 번 계획에 맞춰 분 단위 학습·재학습 단계는 사용하지 않는다.
개인별 매개변수 최적화는 아직 없으며, 문항 형식·변형별 난도 차이는 실제 문항 기록에 보존한다.
20시간 이상 뒤 스스로 맞힌 자동채점 결과를 지연 회상 증거로 집계하며 Hard도 포함한다.
20시간·두 번 기준은 표시 규칙으로 복습 간격을 결정하지 않는다. 시험 점수 예측을 뜻하지 않는다.
강의별 학습량은 고유 요점의 첫 회독 완료/미학습, 고정된 오늘 계획의 새 내용/복습 잔량,
현재 복습 예정 수와 다음 복습 날짜로 표시한다. 첫 회독 목표일은 시험일에서 설정한 여유일을 뺀 날이다.
기존 자료는 고유 문항 단위이며 전체 강의 범위 보장을 뜻하지 않는다. 하루 시간 소진으로
종료한 미완료 항목은 별도로 표시하며 완료로 세지 않는다. 변형·반복 시도는 총범위에 더하지 않는다.

- 분야와 학습 목적에 공통인 판단만 Core에 둔다.
- 목적에 따른 판단은 Profile, 입력 유무에 따른 것은 Adapter에 둔다.
- 용어·분야별 예시는 Domain에 둔다.
- 구조적으로 검증 가능한 조건은 스키마·검증 코드와 함께 바꾼다.
- 실패 이력은 실행 프롬프트에 넣지 않고 [기록](archive/quizgen-cases.md)으로 연결한다.

프롬프트 예시의 강의·동일 주제는 평가 표본에서 제외한다.
예시 출처는 `prompting.py`의 `DOMAINS` 주석을 확인한다.
