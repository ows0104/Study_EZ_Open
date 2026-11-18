# 구현 계획

1. judge.md에 R1·R2를 쓰고 quizbank/root_order.py POLICY를 order-judge/2로.
2. 처음 순서형으로 골랐던 30문항을 새 지시문으로 다시 판정해 운영자 검토(23 순서형·7 아님)와 맞는지 본다.
3. 공개 35편 대상 781문항 전체를 다시 판정해 순서형이 새로 생기거나 빠지는 문항을 본다(올리지 않음).
4. 기존 검사(contracts·quizbank) 실행, PR·병합, 러너 재설치.
