# Spec

- R1. `supplement_round`가 `out_of_scope`로 뺀 문항은 coverage rows의 `evidence`와 `duplicates`에서도 뺀다.
  묶음에 문항이 하나만 남으면 그 묶음을 없앤다. 상태가 `unknown`이 아닌 목표는 남은 근거로
  `covered`/`missing`을 다시 정한다.
- R2. 규칙은 `remove_questions`(operator-exclusions/1)와 한 함수(`forget_in_rows`)를 쓴다. 동작이 갈리지 않게 한다.
- R3. 뺀 문항은 지금처럼 `manifest.offGoalQuestions`에 이유와 함께 남는다.

## 검사

- `tests/quizbank/test_map_relation_guard.py::test_c_a_question_the_late_round_puts_out_of_scope_leaves_the_coverage_rows_too`
  (고침 없이 실패, 고침으로 통과).
- 실패한 실행(548cd177…) 사본을 고친 코드로 재생: 조립 통과, `MODEL CALL medical-0`에서 멈춤(모델 호출은 막아 둠).
