# Plan

사용자 지시(2026-11-16): 「Q248·Q250 빼고 다 프롬프트에서 본질적으로 고쳐줘. 이 예시만이 아니라 더 큰 담론으로써」.
이것을 이 계획의 실행 승인으로 본다. 범위는 [spec.md](spec.md) R1~R6이다.

한 PR(Draft), 브랜치 `feat/existence-question-shape`.

1. 프롬프트(`content/prompts/learning-links/v4/`)
   - `add.md`·`fix.md`: R1·R2 일반 규칙(「한 문항 = 한 연결」 문단)과 R3(존재 문항).
   - `item-review.md`: R1·R2 위반은 design doubt. 존재 문항은 R3로 판정하고, R4의 존재 관계를 whole로 적는다.
   - `presuppose.md`: R5 포인트 원소와 recalled_by.
   - `supplement-normalize-presuppose.md`: R5 합치기와 cue 모양.
2. 코드
   - `studyez_contracts/roots/presuppose.py`: `mark_review(ctx, brief, presuppositions, bank, qids)`(R4)를 추가하고 `order_edges`(R6)를 고친다.
   - `quizbank/connection_generate_v4.py`와 `quizbank/connection_presuppose.py`: 검토·수정 입력에 `mark_review`를 붙인다.
3. 시험: `tests/quizbank/test_presuppose.py`에 R4·R6 케이스를 넣고, 기존 시험과 프롬프트 지문 검사를 돌린다.
4. 로컬 시범: 콜레라 편 presuppose-only/1을 격리 폴더에서 돌리고(약 25분) job 635와 비교한다. 결과는 `release.md`에 쓴다.
5. Draft PR을 열고 사용자에게 보고한다. 운영 반영(병합·러너 재설치·다른 강의 보강)은 사용자 확인 뒤에 한다.
