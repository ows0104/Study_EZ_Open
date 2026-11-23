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

## 변경 범위·대상 파일·순서 (A)

1. `content/prompts/learning-links/v4/add.md`: 「문항 중요도 근거」 절에 R1과 R2를 쓴다.
2. `content/prompts/learning-links/v4/fix.md`: 첫 목록에 R3를 쓰고, question_importance 줄과 「문항 중요도 근거」 절에 R1을 쓴다.
3. `content/prompts/learning-links/v4/item-review.md`: note·fix 줄에 R4를 쓴다.
4. `content/prompts/learning-links/v4/PROVENANCE.md`: 이 변경 한 줄
5. `tests/quizbank/test_basis_covers_answer.py`(새 파일): 지시문 문장을 고정한다.
   #236이 고치는 `tests/runner/test_root_native_v3.py`와 겹치지 않게 새 파일로 둔다.
6. `docs/changes/2026-11-23-basis-covers-answer/measure.py`(작성됨)
7. `quizbank/CLAUDE.md`: /4 줄에 한 문단을 더한다.

`normalize.md`·`importance.py`·러너·서버·DB는 건드리지 않는다.

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
- 복원: git revert. 데이터 변경은 없다.
- 승인 범위: 위 A의 파일, 로컬 검사, Draft PR까지. 병합·러너 재설치·운영 재출제는 하지 않는다.
