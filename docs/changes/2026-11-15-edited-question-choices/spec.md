# 개인 수정한 Main-Quiz 문항의 선지 유지 — 설계

## 요구사항과 수용 기준
intent.md의 세 경우. `server/tests/test_main_quiz_mcq_choices.py` 끝 절이 발문 수정·정답 수정·되돌리기를 확인한다.

## 책임·입출력 계약·오류 상태
`app/root_learning/mcq.py`의 `_resolve`: 개인 수정본(`personalEdited`)이면 판 사본(`bank_snapshot`)의 원문으로
`attachable_v2`/`attachable`을 찾고, 선지를 만들 문항으로 원문(정답 그대로) 또는 고친 단답 문항을 돌려준다.
`attach_front`·`attach_answer`·`entry`가 같은 결과를 쓰므로 앞면 선지와 답면 `mcqCorrectIds`가 어긋나지 않는다. 응답 모양은 그대로.

## 호환성과 데이터 보존
문항·판·asset·개인 수정본·학습 기록·DB 스키마를 바꾸지 않는다. 웹 변경 없음.
