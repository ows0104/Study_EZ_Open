# Main-Quiz 순서 맞추기 화면 — 구현 계획

## 변경 범위·대상 파일·순서
1. 계약: 새 `studyez_contracts/roots/order.py` — 대상 판정(`eligible`), 줄 검사(순열·해시), `select`(씨앗으로 섞기), `correct_ids`.
   검사 `tests/contracts/test_root_order.py`.
2. 생성: 새 `quizbank/root_order.py`(입력 만들기 → 모델 호출 → 코드 검사 → asset JSON)와
   새 `content/prompts/learning-links/order/judge.md`. 검사 `tests/quizbank/test_root_order.py`(모델은 가짜 호출).
3. 러너: 새 `runner/root_order.py`(`--all-published`·`--missing`·`--no-upload`·`--upload-only`, `runner/root_mcq.py`와 같은 모양),
   `runner/connection_generation.py` 선지 호출 뒤 한 줄. 검사 `tests/runner/test_root_order.py`.
4. 서버: `server/app/models/lectures.py` `ASSET_KINDS`에 `root_order` 한 줄, 새 `server/app/root_learning/order.py`(asset 읽기·캐시),
   `server/app/root_learning/mcq.py` `attach_front`·`attach_answer`에서 순서형이면 순서 칸을 붙이고 선지는 뺀다.
   검사 `server/tests/test_main_quiz_order.py`.
5. 웹: 새 `web/src/bank/RootOrder.tsx`(순서 맞추기·답면 비교), `web/src/bank/RootSolve.tsx`(분기·키 처리·response),
   `web/src/bank/quizMode.ts`, `web/src/types/bank.ts`·`rootLearning.ts`(필드), `web/src/bank/main-quiz.css`, 안내 한 줄(`GuidePage.tsx`).
   검사: typecheck, build, `web/tests/`에 순서 화면 렌더·키 처리 검사.
6. 실데이터 확인: 261110_02 판으로 판정을 로컬에서 돌려(`--no-upload`) 순서형 목록을 사람이 확인하고, 로컬 서버(격리 DB)에서 화면 확인.

## 검사 명령과 성공 조건
- 루트: `python -m pytest tests/contracts tests/quizbank tests/runner -q` 통과.
- `server/`: `PYTHONPATH=.. .venv/Scripts/python.exe -m tests root main_quiz route_contract` 통과(worktree 계약을 쓰도록 PYTHONPATH 지정).
- `web/`: `npm run typecheck`, `npm run build`, 새 검사 통과.
- 새 서버 검사는 고치기 전 코드에서 실패하는 것을 확인한다.

## 위험·복원·승인할 범위
- 판정이 틀리면 순서형이 아닌 나열이 순서 화면으로 나온다. 줄마다 근거를 남기고, 문제가 있는 줄은 asset에서 빼서 다시 올리면 된다. 문항·기록은 손대지 않는다.
- asset이 없거나 깨졌으면 지금 화면으로 돌아간다. 복원은 asset 삭제나 커밋 revert.
- 승인받을 것: ① 이 계획(구현 시작) ② master 병합(=API·웹 자동 배포) ③ 공개 강의 전부에 판정을 돌려 올리기(모델 호출 강의당 1회).
