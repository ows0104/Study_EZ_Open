# Main-Quiz 오늘 계획: 선행 과제가 빠진 과제를 plan에 넘기지 않기 — 설계

## 요구사항과 수용 기준

- R1 준비 상태: /2·/4 판에서 선행 과제(`task_dependencies`: 문항 선행 + 목표 선행)가 준비되지 않은 과제는 준비되지 않는다.
  bank_source가 quizbank든 standalone이든 같다. 이유는 기존 문구 「명시적 선행 문항이 준비되지 않음」.
- R2 중요도 필터: 고른 중요도는 오늘 계획의 **후보**만 좁힌다. 후보 과제의 선행이 준비되어 있고 아직 평가하지 않았으면,
  중요도와 상관없이 order_plan이 「명시적 선행 문항」으로 앞에 둔다. 이미 평가한 선행은 다시 내지 않는다(order_plan 기존 규칙).
- R3 필터를 안 쓸 때(모두 선택) 계획은 이전과 같다(`plan(..., focus=None)` == 이전 호출).
- 수용: `server/tests/test_root_prereq_closure.py` — 선행 제외 → 의존 과제도 빠짐·overview/entry/catalog 200·세션 2과제,
  선행을 Optional로 두고 Optional 끔 → 선행이 앞에 끌려옴·200, 평가한 선행은 안 끌려옴, 학습 기록 불변.

## 책임·입출력 계약·오류 상태

- `content.availability(db, content, user_id)`: 반환 `(available, problems)`의 available은 언제나 선행에 대해 닫혀 있다.
  공용 함수 `content.close_prerequisites(doc, available, problems)`로 뺐다(/2·/4가 아니면 그대로).
- `planning.plan(doc, events, available, now, policy, focus=None)`: `available`은 닫힌 집합, `focus`는 그 부분집합(후보).
  order_plan의 확인은 `available`로 한다.
- `routes/root_learning.overview_data`: 좁힌 경우에만 `focus`를 넘긴다. 응답의 `focus.counts`·summary·questionProgress는 그대로 `available` 기준.

## 호환성과 데이터 보존

- 개인 제외한 선행에 기대는 과제는 이제 「준비 안 됨」으로 세어진다(`preparationProblems`가 늘 수 있다). quizbank 판의
  일시중지·제외와 같은 규칙이다. 제외를 Z로 되돌리면 다시 준비된다. 이벤트는 쓰지도 지우지도 않는다.
- 필터 회차의 과제 수(시작 버튼 배지)는 끌려온 선행만큼 늘 수 있다. 세션 ID는 과제 목록으로 정해지므로 같은 입력이면 같다.
- 모두 선택이면 계획·세션 ID 불변(R3).
