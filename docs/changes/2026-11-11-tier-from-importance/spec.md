# Spec

- R1 `generation_v3.AUTHORED_QUESTION`·`AUTHORED_CONCEPT`: 은행 문항·개념 형식에서 `tier`를 빼고 `importance`를
  enum [2, 3, 4, 5]로 둔다. `ADD_OUTPUT`·`FIX_OUTPUT`(v4는 이것에 question_importance를 더함)이 이 형식을 쓴다.
  러너의 acceptance schema가 같은 정의라 모델 출력에 tier가 있으면 러너 검사에서 거부된다.
- R2 `merge_added`·`merge_fixes`·`check_added`·`check_fixed`: 출력의 tier를 버린 뒤 형식을 검사하고(이전 실행의 캐시
  출력 호환), 합칠 때 `TIER_BY_IMPORTANCE`(bank 3.3 표의 역)로 tier를 채운다.
- R3 `connection_generate_v3._bank_findings(bank, sources, attempts)`: `quality_reasons`(권고)는 수정 횟수 0인 문항에만
  붙인다. validate_bank errors·검수 이력 표현은 그대로. /3·/4의 묶음 수정 루프와 맥락 수정이 attempts를 넘긴다.
- R4 프롬프트: v4 add.md·fix.md는 tier 대신 importance만 쓰라고 바꾼다. v3 add.md·fix.md는 v2 문단 원문 보존 검사
  때문에 원문 문단 뒤에 같은 지시 문단을 더한다. 프롬프트 지문이 바뀌므로 기존 /3·/4 ledger를 이어 가려면 `--resume`.
