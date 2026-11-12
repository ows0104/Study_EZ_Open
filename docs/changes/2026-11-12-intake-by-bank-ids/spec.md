# Main-Quiz 접수: 문항 오류 판별을 문제은행의 실제 문항 번호로 — 설계

## 요구사항과 수용 기준
- `_question_of(text, question_ids)`: 머리가 주어진 번호 집합에 있으면 그 번호, 아니면 기존 `_QID` 규칙.
- `_bank_findings`·`intake_rejections`(v3·v4 접수, 앞 단계 문제은행 검사)가 문제은행의 번호 집합을 넘긴다.

## 책임·입출력 계약·오류 상태
- `quizbank/connection_generate_v3.py`, `connection_generate_v4.py`, `runner/root_front.py`. 계약·서버·DB·지시문 불변.

## 호환성과 데이터 보존
- 번호 집합을 안 넘기는 호출과 `Q…` 번호의 동작은 그대로다.
