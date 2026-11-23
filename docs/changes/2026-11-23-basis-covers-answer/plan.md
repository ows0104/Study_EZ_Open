# Main-Quiz /4 중요도 근거가 답 전체를 덮게 — 구현 계획

## 선택지 (사용자 결정)

검토가 제안한 「다른 물음」을 새 문항으로 만들지가 갈림길이다.
고치기 단계는 지금 받은 ID의 교체본만 낼 수 있다.

- **A. 지시문만 (권장, 이 PR)**: R1~R4, R6.
  - 같은 ID를 넓히는 것과 근거가 답 일부만 덮는 것을 막는다.
  - 검토의 다른 물음 제안은 note의 「별도 문항: …」으로만 남고, 새 문항은 생기지 않는다.
  - 목표가 요구하는 내용은 커버 확인·추가 출제·presuppose/1이 이미 채운다. 잃는 것은 어느 목표에도 없는 제안뿐이다.
- **B. A + 고치기가 새 문항을 냄 (R5)**: 아래 코드가 더 바뀐다.
  - `generation_v4.FIX_OUTPUT`에 `split_questions`를 더하고, 묶음마다 겹치지 않는 새 ID 범위를 준다(동시 묶음 때문).
  - `check_fixed`·병합(`merge_added`)을 고친다.
  - `fix_round`가 새 문항을 다시 검토·커버 재확인에 넣는다. 되돌린 고치기의 새 문항은 함께 버린다.
  - manifest와 검사도 바뀐다.
  - 문항 수가 늘고 검토·고치기 호출이 늘어난다. 별도 PR로 하는 편을 권한다.

**결정(2026-11-23, 사용자 「A와 B 둘다 해도될듯?」)**: A와 B를 둘 다 한다.
B가 A의 fix.md 문장(「적용하지 않은 이유를 exam_rationale에」)을 바로 다시 고치므로 한 PR에 둔다.

## 변경 범위·대상 파일·순서 (A)

1. `content/prompts/learning-links/v4/add.md`: 「문항 중요도 근거」 절에 R1과 R2를 쓴다.
2. `content/prompts/learning-links/v4/fix.md`: 첫 목록에 R3를 쓰고, question_importance 줄과 「문항 중요도 근거」 절에 R1을 쓴다.
3. `content/prompts/learning-links/v4/item-review.md`: note·fix 줄에 R4를 쓴다.
4. `content/prompts/learning-links/v4/PROVENANCE.md`: 이 변경 한 줄
5. `tests/quizbank/test_basis_covers_answer.py`(새 파일): 지시문 문장을 고정한다.
   #236이 고치는 `tests/runner/test_root_native_v3.py`와 겹치지 않게 새 파일로 둔다.
6. `docs/changes/2026-11-23-basis-covers-answer/measure.py`(작성됨)
7. `quizbank/CLAUDE.md`: /4 줄에 한 문단을 더한다.

## 변경 범위·대상 파일·순서 (B, fix-splits/1)

8. `studyez_contracts/roots/generation_v4.py`: `FIX_SPLIT_OUTPUT`(`split_questions`, 문항마다 `split_from`)와 `fix_schema(ctx)`.
   `check_fixed`가 입력에 `allowed_split_question_ids`가 있을 때만 그 스키마를 쓰고 `check_splits`로 묶는다.
   - 새 ID는 허용 범위 안, split_from은 이 출력이 고친 문항, concept_id는 같고 point_ids는 그 안, conflict_id는 없거나 같고,
     prerequisites는 원래 문항이나 그 선행 문항
   - 병합은 `merge_fix_output`: 고친 문항은 `v3.merge_fixes`, 새 문항은 `v3.merge_added`(tier·cloze·ID 검사 그대로)
9. `runner/root_native_json.py`: v4 fix 단계의 스키마를 `v4.fix_schema(ctx)`로(추가 출제의 `add_schema`와 같은 방식).
10. `quizbank/connection_generate_v4.py`:
    - 새 ledger에 `fixSplits`(fix-splits/1). 없는 ledger는 입력·출력이 이전 그대로다.
    - 묶음 b의 새 ID 범위는 실행이 쓴 모든 ID(접수·현재·목표 밖으로 뺀 문항) 다음부터 `REVIEW_BATCH × FIX_LIMIT`개씩.
      동시 묶음이 같은 ID를 쓰지 않고, 순차로 돌아도 같은 ID가 나온다. 임상 정리 고치기는 모든 범위 뒤.
    - 새 문항은 고친 문항과 함께 다시 검토되고(첫 검토), 원래 문항의 목표 커버 재확인에 함께 들어간다.
      원래 문항의 고치기가 되돌려지면 새 문항도 함께 버린다. 새 문항은 그 묶음의 다음 고치기 회차 대상이 된다.
    - manifest `fixes` 행에 `split_questions`(그 고치기가 낸 새 ID)를 단다. 결과 계약은 그대로 통과한다(새 문항은 접수 문항이 아니다).
11. `quizbank/connection_batches.py`: 동시 묶음이 덧붙인 문항을 묶음 순서로 합치고, 그 문항의 검토·근거·그림도 가져온다.
12. `tests/quizbank/test_root_generation_v4.py`: 합성 모델이 새 입력에 `split_questions: []`를 낸다.

`normalize.md`·`importance.py`·서버·DB는 건드리지 않는다.

## 검사 명령과 성공 조건

- `python -m pytest tests/quizbank/test_basis_covers_answer.py -q`
  - 지시문을 고치기 전에는 실패하고, 고친 뒤에는 통과한다.
- `python scripts/development.py verify 2026-11-23-basis-covers-answer --check regression -- python -m pytest tests studyez_contracts -q -p no:cacheprovider`
  - 전부 통과한다(실패가 있으면 master에서도 나는지 구분해 적는다).
- `python docs/changes/2026-11-23-basis-covers-answer/measure.py --runs <메인 체크아웃>/runs`
  - 끝까지 돌고 세 예를 보고한다.
- 모델 실행(재생)은 하지 않는다. 지시문 효과는 새 러너의 첫 강의에서 `measure.py`로 본다(release.md).

## 위험·복원·승인할 범위

- 위험 1: 모델이 근거를 너무 보수적으로 빼서 Core가 줄어든다.
  B 측정의 93개가 상한 쪽 신호다. 새 실행 뒤 `measure.py`와 tier 분포를 비교한다.
- 위험 2: 고치기가 정당한 수정(틀린 정답 교체·존재 원소 채우기)까지 막는다. 예외 셋을 지시문에 명시하고 검사로 고정한다.
- 위험 3: 지시문 해시가 바뀌어 진행 중 실행 이어 가기가 막힌다. 병합·러너 재설치는 러너 담당 세션과 맞추고, 사용자 승인 없이 하지 않는다.
- 위험 4(B): 고치기가 새 문항을 너무 많이 낸다. 한 회차의 허용 ID는 그 회차 고칠 문항 수만큼이고, 지시문이 「근거를 올리려고 나누지 않는다」를 둔다.
  새 실행 뒤 `fixes[].split_questions` 수를 센다.
- 위험 5(B): 새 문항이 목표에 안 붙는다. 그런 문항은 기존 늦은 보충(review-relations/2 C·D)이 받는다.
- 복원: git revert. 데이터 변경은 없다. 되돌린 뒤 새로 시작한 실행은 `fixSplits` 표시가 있어도 옛 코드가 그 키를 읽지 않는다.
- 승인 범위: 위 A·B의 파일, 로컬 검사, Draft PR까지. 병합·러너 재설치·운영 재출제는 하지 않는다.
