# 목표 중요도 근거의 같은 쪽 중복 제거 — Implementation Plan

1. `_unique`를 추가하고 `target_axes`에 적용한다.
2. 회귀 검사를 추가한다: `tests/contracts/test_importance_basis.py::test_a_page_the_basis_names_twice_is_one_target_reference`.
3. 확인
   - 공개 판 1c484a7b·fa71412a·26110803을 재검증한다.
   - 실패한 아데노 실행을 모델 호출 없이 재생한다.
   - 계약 검사 전체를 돌린다.
4. PR을 병합한다(API 자동 배포). 이어서 러너를 재설치한다.
5. 실패한 실행을 이어 갈지는 사용자가 정한다. 「이어 하기」를 누르면 남은 의학 검토부터 돈다.
