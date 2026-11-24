# 늦은 보충 뒤 문맥 고치기의 검토가 조립에 안 닿음

## 문제와 사용자 효과
2026-11-24 261124_02 피부근염(강은하) Main-Quiz가 「연결 자동출제 보류: assessment4: every prerequisite needs one check」로
멈춰 Quiz Bank를 만들지 못했다(로그 `runs/agent.261124_02.log`, generation `aadee987…`).

저장된 단계 출력으로 재생하면 어긋난 것은 하나다. DM-Q065의 검토가 선행 DM-Q055를 검사했는데, 은행의 DM-Q065에는 그 선행이 없다.
- 문맥 고치기(`v4-fix-context-0`)가 DM-Q065의 선행 DM-Q055를 뺐고, 재검토(`v4-review-context-1`)는 선행 검사 0개로 맞게 답했다.
  모델 출력은 둘 다 맞다.
- `quizbank/connection_generate_v4.py`의 늦은 보충(`reviews = {… if q not in gone}`)과 사람이 뺀 문항(`remove_questions`)은
  지역 변수 `reviews`를 새 dict로 바꾼다. 문맥 고치기 회차의 `fix_round`는 재검토를 `S.reviews`(옛 dict)에 적는다.
  조립은 지역 `reviews`를 읽어 고치기 전 검토를 봤다.
- 늦은 보충이나 사람이 뺀 문항 **그리고** 문맥 고치기가 같이 도는 편에서만 난다. 선행이 바뀌지 않으면 멈추지는 않지만
  조립·인용 맞춤이 옛 검토(근거 쪽·관계)를 쓴다.

## 범위와 성공 기준
- 문맥 고치기 회차 앞뒤로 `reviews`를 `S.reviews`와 맞춘다(호출부 2줄).
- 성공: 261124_02 재생이 선행 검사·조립을 지나 의학 검토(`medical-0`)까지 간다. 새 검사는 고침 없이 실패한다.
- 넣지 않는 것: 프롬프트·계약·서버·웹·DB. 이미 공개된 판은 건드리지 않는다.
