# Main-Quiz cloze 정답 단위를 발문 빈칸에 맞춤 — 구현 계획

## 변경 범위·대상 파일·순서
1. `server/app/root_learning/content.py`: `answer_units(q)` 추가, `answer()`가 사용(R1).
2. `studyez_contracts/roots/generation_v3.py`: `cloze_units(bank)`, `merge_added`·`merge_fixes`에서 호출(R2·R3).
3. `quizbank/connection_generate_v3.py`, `quizbank/connection_generate_v4.py`: `_intake`에서 호출, manifest `intakeClozeUnits`(R3).
4. 검사: `server/tests/test_main_quiz_cloze_units.py`(실제 두 문항 모양), `tests/contracts/test_generation_v3.py`
   (`test_cloze_answer_units_follow_the_stem_blanks_where_questions_enter`).

## 검사 명령과 성공 조건
- `python -m pytest tests/contracts tests/quizbank tests/runner` 전부 통과.
- `server/`에서 `.venv/Scripts/python.exe -m tests root main_quiz` 전부 통과(worktree에서는 `PYTHONPATH`로 이 checkout의 계약).

## 위험·복원·승인할 범위
- 위험: 진행 중 실행을 새 러너로 이어 하면 멈출 수 있다(spec 「호환성」). 러너 재설치는 도는 실행이 없을 때.
- 복원: git revert. 데이터 변경이 없으므로 되돌리면 이전 표시로 돌아간다.
- 승인 범위: 위 파일들. 프롬프트·DB·게시된 판은 건드리지 않는다.
