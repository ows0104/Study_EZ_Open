# Main-Quiz 긴 나열 답 줄이기 — 구현 계획

## 변경 범위·대상 파일·순서

1. **판정기**
   - 파일:
     - `quizbank/root_long_list.py`(root_order.py와 같은 틀: Codex CLI 하위 프로세스, 묶음 단위 호출)
     - `content/prompts/learning-links/long-list/judge.md`
     - `studyez_contracts/roots/long_list.py`(대상 고르기·출력 검사)
     - 검사 `tests/quizbank/test_root_long_list.py`
   - 근거 쪽 원본 그림을 함께 넘긴다.
   - 대상은 공개판 55편 150장(답 6개 이상)이다. 모델 호출은 강의별 1~2회, 약 60회다.
2. **판정 실행과 사용자 확인**
   - 공개판을 읽기 전용으로 받아 판정을 돌린다.
   - 결과는 `runs/_development/2026-11-25-long-list-answers/`에 남긴다.
   - grouped / ungrouped 목록과 ungrouped의 두 후보 예시를 페이지로 보여 드리고 R2 방법을 정한다.
3. **생성 규칙**
   - 대상: `content/prompts/learning-links/v4/add.md`·`fix.md`·`supplement-normalize-presuppose.md`.
     R1을 넣고, R2는 2에서 정한 방법대로 넣는다.
   - 프롬프트 지문 기록(prepare-prompts)을 갱신한다.
   - `presuppose.py`의 「존재 목표당 문항 하나」 가정을 확인하고 필요하면 고친다. 검사를 붙인다.
4. **루프스 시범**
   - `runs/fill-goals.json`에 261123_06의 rewrite(Q090·Q083·Q072·Q115·Q111·Q121 등 판정 결과)와 goals를 적는다.
   - 모의 실행(`C:/sez/rp/dryrun_fill.py` 방식)으로 받을 목표가 있는지 먼저 본다.
   - 받을 목표가 없는 묶음이 있으면 멈추고 채우기 확장을 따로 설계해 승인을 받는다.
   - 운영 보강 요청 1건을 넣고 결과를 보여 드린다.
5. **나머지 강의**
   - 시범 결과를 보신 뒤 강의별로 넣는다. 한 번에 2편씩이다.
6. 끝나면 대시보드 행을 지우고, 변경 기록·메모를 갱신한다.

1·3은 PR 하나(Draft)로 묶는다. 4·5는 운영 요청이라 PR이 아니다.

## 검사 명령과 성공 조건

- `python -m pytest tests/quizbank/test_root_long_list.py tests/quizbank/test_connection_presuppose.py -q`
- 저장소 회귀: [docs/commands.md](../../commands.md)의 regression.
  - worktree 검사는 `PYTHONPATH=..`로 이 worktree의 studyez_contracts를 쓴다
    ([[server-venv-imports-main-checkout-contracts]]).
- 프롬프트 지문: verify build. 종료 2는 bank-prompt.json LF 재기록일 수 있다([[verify-build-exit-2-is-prompt-rewrite]]).
- 시범의 성공 조건: Q090이 31쪽 한 열을 묻는다. 새 묶음 문항이 생긴다. Q090 외 공개 과제 승계가 100%다.

## 위험·복원·승인할 범위

- 판정 약 60회 Codex 호출은 정해진 경로의 새 실행이다. 사용자 「어 그렇게 하자」(2026-11-25)로 승인된 범위로 본다.
- 운영 보강 요청은 강의마다 학습 기록 일부가 끊기는 쓰기다.
  - 시범 1건은 위 승인 범위다.
  - 나머지 강의는 시범 결과를 보신 뒤 다시 묻는다.
- 복원: 보강판이 잘못되면 이전 공개 revision으로 되돌린다(공개 관리 API). 프롬프트는 git revert로 되돌린다.
- R2 방법은 정하지 않았다. 판정 결과를 보시기 전에 규칙으로 넣지 않는다.
- 겹침: 대시보드 P3 「답 강조」(add·fix 같은 파일, 시작 전)와 PR 순서만 맞추면 된다.
