# 구현 기록 — 2026-11-26

## 한 것

- 지시문: bankPrompt 1.85, v4 presuppose·normalize·add·fix·item-review, map-tree/bank-task-v4 (plan 1·2단계).
- 코드: `importance-basis/3`(`carries`, `off_level`), `answer-level/1`(검토 칸 `off_level_exam_years`, `carried_by`, 조립·검증 전달) (plan 3단계).
- 보강(`connection_presuppose.py`)·재배치(`connection_replace.py`)·중복 재판정(`connection_dedupe.py`)은 이어받는 판에 `answerLevel`이 있으면 같은 계산을 넘긴다.
  plan에는 「인자를 넘기지 않는다」고 썼으나, 새 실행으로 만든 판을 이 경로들이 이어받는 기존 검사 14개가 깨져서 바꿨다. `answerLevel`이 없는 공개판은 그대로다.

## 검사

- `python -m pytest -q -p no:cacheprovider tests --deselect tests/runner/test_desktop_control.py::test_shortcut_installer_supports_korean_filename_in_windows_powershell`
  → 3221 passed, 5 skipped, 1 deselected (9분 39초). 그 뒤 로그 한 줄과 문서만 고쳤고, 고친 파일의 검사(46개)를 다시 돌려 통과했다.
- 새 검사: `tests/contracts/test_answer_level.py` 18개, `tests/quizbank/test_root_generation_v4.py`에 끝단 1개.
- **미실행**: `web/tests/bank-prompt-current.test.cjs` — 이 worktree에 `web/node_modules`가 없다. `web/public/bank-prompt.json`은 `node scripts/prepare-prompts.mjs`로 1.85로 다시 만들었다. PR을 Ready로 바꾸면 CI가 돈다.
- **미실행**: 서버 검사(`server/tests`). 서버 코드는 바꾸지 않았다. 서버가 쓰는 계약(`studyez_contracts`)의 결과 검증은 `tests/contracts`·`tests/quizbank`가 돌린다.

## 피부근염 로컬 판으로 다시 계산 (읽기 전용, 문항은 다시 쓰지 않음)

- 기존 판을 `answerLevel` 없이 다시 조립 → 저장된 문서와 같다.
- `answer_level=True`로 조립 → 등급이 오른 문항 12개, 내린 문항 0개(spec 「구현 뒤 다시 계산한 값」).
- 지시문이 실제로 문항을 어떻게 바꾸는지는 아직 보지 못했다. 모델을 돌려야 한다(plan 5단계, 따로 승인).
