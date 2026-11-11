# Main-Quiz 같은 문항 반복 제거 — 구현 계획

## 변경 범위·대상 파일·순서

1. `content/prompts/learning-links/v4/coverage.md`(R1), `normalize.md`(R2), `add.md`(R3), `PROVENANCE.md`.
2. `studyez_contracts/roots/generation_v4.py`: `add_input(rows=)`, `ADD_OUTPUT` 최소 0, `GOAL_DUPLICATES` 상수.
3. `quizbank/connection_generate_v4.py`: fresh 표시, 추가 입력에 rows, 빈 추가 처리, 재확인 questions 확대, `_merge_row` 묶음 필터.
4. `server/app/root_learning/planning.py`: `plan_tasks` 방향별 순번 배열(R5).
5. 검사: `tests/quizbank/test_goal_duplicates.py`, `tests/contracts`(add_input·ADD_OUTPUT), `server/tests/test_root_learning_v4.py`.
6. 문서: `quizbank/CLAUDE.md`, `server` 쪽 계획 설명(planning docstring), README 「한 장 그림」에 닿으면 함께.
7. PR(Draft → Ready 한 번) → master 병합(=API·웹 자동 배포) → 야간 일괄 출제에서 그때 도는 강의가 끝난 뒤 러너 재설치·재가동.

## 검사 명령과 성공 조건

- regression: `python -m pytest tests/contracts tests/quizbank tests/runner -q` (anaconda python, `PYTHONIOENCODING=utf-8`).
- server: `server/`에서 `PYTHONPATH=.. .venv/Scripts/python.exe -m tests root`.
- 피코르나 저장 결과 무모델 재생(A4): 스크립트 출력으로 과제 수 확인.
- 실패·미실행·기존 결함은 release.md에 구분해 적는다.

## 위험·복원·승인할 범위

- 위험: R1로 커버가 후해져 실제로 빠진 내용이 covered가 될 수 있다. 범위를 「해석상 주의」로 좁혀 적었다. 실제 판정은 재설치 뒤 첫 강의의
  coverage 단계 출력과 readiness로 본다.
- 위험: R3로 추가 문항이 줄 수 있다. 줄어드는 것은 asked 문항과 답이 같은 것뿐이어야 한다. 첫 강의의 add 출력으로 본다.
- 위험: R5는 공개된 강의의 순서를 바꾼다. 과제·기록은 그대로라 `git revert`와 이전 Cloud Run revision으로 되돌린다.
- 복원: 코드 `git revert`, 러너는 `.runtime/main-quiz-c45caf111ea6` 설치본이 남아 있다.
- 승인: 구현·병합·러너 재설치는 사용자 2026-11-12 요청이 근거다. 공개 판 교체·재출제·모델 재생은 이 작업에 없다.
