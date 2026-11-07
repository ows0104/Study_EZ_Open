# Measure recall load and structural answer cues in the bank checker — 설계

## 요구사항과 수용 기준

`quality_errors(bank)` 가 기존 정답 노출 검사에 더해 다섯 가지를 잰다. 반환 계약은 그대로
`(errors, warnings)` 이고 **새 측정은 전부 warnings** 다.

| 측정 | 무엇을 보는가 | 선 | 메시지 자리 |
|---|---|---|---|
| 예/아니오 축 | basic·list 의 정답이 극성(아니다/없다/~할 수 없다/예/그렇다)인가 | 선 없음 — 한 건이면 적는다 | 문항별 |
| 정답 쏠림 | 극성 문항(ox 포함) 전체의 정답이 한쪽뿐인가 | 3문항 이상 | 은행 전체 |
| 단정어×부정 | 발문의 단정어와 부정 정답이 겹치는가 | 선 없음 | 문항별 |
| 회상 부담 | basic 정답 길이 · list 정답 길이 · list 단위 길이 · 단위 수 | 50 · 90 · 30 · 6 | 문항별 |
| 형식 쏠림 | 회상 부담이 큰 문항이 있는데 cloze·객관식이 0개인가 | 20문항 이상 | 은행 전체 |

### 선을 어디서 가져왔는가
규칙이 아니라 **건강한 모집단의 꼬리**다. 2026-11-08 운영 `quiz_bank` 35편 3,103문항
(웹 정본 프롬프트 산출물)에서 쟀다.

| | p50 | p90 | p97 | p99 | 최대 |
|---|---|---|---|---|---|
| basic 정답 길이 | 15 | 38 | 49 | 59 | 84 |
| list 정답 길이 | 30 | 63 | 92 | 112 | 156 |
| list 채점 단위 길이 | 10 | 23 | 32 | 46 | 73 |
| list 단위 수 | 2 | 4 | 5 | 5 | 6 |

cloze 0인 편 1/35 · 객관식 0인 편 0/35 · basic·list 가 예/아니오로 답하는 것 1/1,813(0.06%).

같은 자를 2026-11-07 Main-Quiz 한 편(98문항)에 대면 basic>50자 15.8%, 단위>30자 16.4%,
예/아니오 축 6/97(6.2%), cloze·객관식 0개다.

### 수용 기준
- 새 Main-Quiz 98문항 → errors 0, warnings 36(예/아니오 축 6 · 회상 부담 25 · 단정어×부정 3
  · 정답 쏠림 1 · 형식 쏠림 1). Q003·Q080 이 이름으로 나온다.
- 운영 Quiz Bank 35편 → 새 경고 합계 62, 편당 중앙 2 · 최대 10, errors 증가 0,
  예/아니오 축 0편 · 형식 쏠림 0편 · 정답 쏠림 5편(OX 정답이 전부 X인 약리 편들).
- schema_version 3.0 은행은 아무 것도 재지 않는다(기존 조기 반환 유지).

## 책임·입출력 계약·오류 상태

- `studyez_contracts/bank` 경계를 지킨다 — 표준 라이브러리(`collections.Counter`)와 같은
  묶음의 순수 모듈만 쓴다. DB·FastAPI·모델 호출 없음.
- 공개 이름: `answer_polarity(question)`, `recall_chars(question)`,
  `LONG_ANSWER_CHARS`·`LONG_UNIT_CHARS`·`MAX_ANSWER_UNITS`·
  `NARROW_FORMAT_MIN_QUESTIONS`·`POLARITY_MIN_QUESTIONS`.
  선을 조이거나 풀 때 코드가 아니라 이 상수만 고친다.
- `validate_bank(..., check_quality=False)` 경로는 영향 없다 — 구조 검사만 보는 호출
  (`connection_parallel.py`, `run.py`)은 그대로다.
- 오류 상태 없음. 측정은 예외를 던지지 않고, 걸리면 경고 한 줄을 남긴다.

### 재지 않는 것
- **cloze 프레임에는 길이 선을 긋지 않는다.** cloze 의 `answer` 는 빈칸을 채운 문장
  전체(`normalize_cloze`)이므로 그 길이는 회상 부담이 아니다. 조일 곳은 basic 의 정답이다.
- 한 글자 `O`/`X` 는 ox 정답일 때만 극성이다. basic 정답 `Olaparib`·`O₂`·`OCT1`·`OKT3` 는
  극성이 아니다 — 첫 판에서 이 자리를 운영 은행에서 34번 잘못 짚었고, 회귀 검사로 고정했다.
- basic 의 채점 단위는 정답 하나뿐이라 단위 길이 선을 묻지 않는다. 물으면 위의 정답 길이
  선이 뜻을 잃는다(첫 판에서 건강한 basic 의 20%가 걸렸다).
- 단정어는 그 자체로 적지 않는다. 정본 §3.5 가 일괄 금지를 금지한다 — 부정 정답과
  겹칠 때만 적는다.

## 호환성과 데이터 보존

- 기존 errors 문구·개수 불변. `tests/quizbank/test_quizbank.py` 의 실물 은행 errors 동치
  검사가 그대로 통과한다(측정을 errors 에 넣으면 깨진다).
- 문항·ID·학습 기록·검수 이력은 건드리지 않는다. 저장된 은행을 다시 쓰지 않는다.
- 새 경고는 다음 검증 때부터 생긴다. 이미 저장된 `quiz_bank.validation`·`root_content` 는
  그대로 남고, 다시 검증하는 경로에서만 갱신된다.
- 소비처: 루트 파이프라인이 `validate_bank(bank, source_ids)` 결과를 그대로 넘기므로
  새 경고가 `root_generation.py` 의 `issues`, `root_learning.py` 의 `reviewIssues`,
  그리고 repair 단계 입력의 `validation` 으로 흐른다. 서버·웹 코드 변경 없음.
