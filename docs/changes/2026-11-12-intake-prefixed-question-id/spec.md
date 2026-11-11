# Main-Quiz 접수: 접두어가 붙은 문항 번호의 오류도 그 문항에 귀속 — 설계

## 요구사항과 수용 기준
- `_QID`가 `<영숫자 접두어>-Q…` 형식도 문항 번호로 읽는다. `_bank_findings`·`intake_rejections`가 함께 쓴다.

## 책임·입출력 계약·오류 상태
- `quizbank/connection_generate_v3.py`만 바뀐다. 계약·서버·DB·지시문 불변.

## 호환성과 데이터 보존
- `Q…` 번호의 동작은 그대로다. 기존 실행의 단계 입력은 바뀌지 않는다.
