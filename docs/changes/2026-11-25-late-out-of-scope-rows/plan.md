# Plan

1. `quizbank/connection_generate_v4.py`: `remove_questions`의 판정표 정리 부분을 `forget_in_rows(rows, goals, gone)`로
   빼고, `supplement_round` 끝에서 부른다.
2. 재현 검사 하나(`OutOfScopeLateModel`).
3. 병합 뒤: 러너 설치본을 새로 깔고, job 751을 `--resume`으로 잇는다(저장된 단계는 그대로 쓰고 의학 검토부터 돈다).

승인: 병합(= API·웹 자동 배포)·러너 교체·751 재개는 사용자 확인 뒤.
