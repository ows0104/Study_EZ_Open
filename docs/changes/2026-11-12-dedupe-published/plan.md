# Main-Quiz 공개 판 중복 재판정·선지 병렬 — 구현 계획

## 변경 범위·대상 파일·순서
1. 서버 `server/app/routes/root_generation.py`(R1), 검사 `server/tests/test_root_restart.py`.
2. 생성기 `quizbank/connection_dedupe.py`(새), `quizbank/connection_generate.py`(`--duplicates-of`), 검사 `tests/quizbank/test_dedupe_published.py`.
3. 러너 `runner/connection_generation.py`(R2), 검사 `tests/runner/test_dedupe_published_runner.py`.
4. 선지 `quizbank/root_choices.py`·`runner/root_choices.py`(R4), 검사 `tests/quizbank/test_root_choices.py`·`tests/runner/test_root_choices_publish.py`.
5. 문서 `quizbank/CLAUDE.md`.
6. PR(Draft → Ready 한 번) → master 병합(=API·웹 자동 배포) → 러너 재설치(돌고 있는 강의가 없을 때).
7. 운영(사용자 요청 범위): 5편에 「중복만 다시 판정」 요청 → 러너가 처리·게시 → 공개된 감염과 면역 전부에 선지 작성·업로드.
   영수증 `runs/_development/2026-11-12-dedupe-published/receipt.jsonl`.

## 검사 명령과 성공 조건
- regression: `python -m pytest tests/contracts tests/quizbank tests/runner -q` (anaconda python, `PYTHONIOENCODING=utf-8`).
- server: `server/`에서 `PYTHONPATH=".;.." <main>/server/.venv/Scripts/python.exe -m tests root`.
- 실제 5편 무모델 재생(A4): scratchpad 스크립트, 과제·커버 행이 같고 검증 통과.
- 실패·미실행·기존 결함은 release.md에 구분해 적는다.

## 위험·복원·승인할 범위
- 위험: 재판정이 실제로는 다른 내용을 묻는 두 문항을 중복으로 묶으면 그 목표의 과제가 줄어든다. 묶음은 근거 문항끼리만 받고,
  바뀐 묶음은 manifest `duplicatesOnly.changedGroups`에 남아 확인할 수 있다. 문항은 은행에 남는다.
- 위험: 새 판 게시로 그 강의의 학습 기록이 넘어가지 않는다(사용자 확인). 옛 판·기록은 DB에 남는다.
- 위험: 선지 병렬로 동시 Codex 세션이 최대 2강의 × 3묶음 = 6. 출제 일괄(일꾼 2 × 묶음 3)과 같은 수준이다.
- 복원: 코드는 `git revert`. 판은 옛 판이 DB에 있으므로 control을 옛 판으로 돌릴 수 있다(별도 조치). 선지 asset을 지우면 선지가 꺼진다.
- 승인: 구현·병합·러너 재설치·5편 새 판 교체·선지 업로드는 사용자 2026-11-12 요청과 질문 답(intent.md 근거)이 범위다.
  위장관·피부연조직(261102_06)의 중복 재판정은 범위 밖. 다른 과목은 범위 밖.
