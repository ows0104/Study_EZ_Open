# 예습 덱 파일 이름에서 Windows 금지 글자를 뺀다 — 구현 계획

## 변경 범위·대상 파일·순서
1. `runner/deck.py` `apkg_name`: `RE_FS_UNSAFE`를 빼고 공백을 줄인다(R1). 주석·docstring에 까닭을 적는다.
2. `tests/runner/test_apkg_name_unsafe.py`: 실제 261125_07 입력으로 R1~R4를 검사한다. 고치기 전에는 실패해야 한다.
3. Draft PR → (사용자 승인 뒤) Ready·병합.
4. 병합 뒤 러너를 새로 설치하고 `.runtime/main-quiz-<sha12>`, 251126_15만 `python -m quizgen.prequiz.run --resume …/prequiz/261123-1826`로 잇는다. 이어서 `prequeue`가 계약 모양(`pre_run.meta.json`)을 쓰게 한다.

## 검사 명령과 성공 조건
- `python -m pytest tests/runner/test_apkg_name_unsafe.py -q`: 고치기 전 2 실패, 고친 뒤 4 통과.
- `python -m pytest tests/runner tests/quizgen -q`: 모두 통과.

## 위험·복원·승인할 범위
- 위험이 낮다. 금지 글자가 든 이름만 달라지고, 그런 이름은 지금 모두 빌드에서 멈춘다.
- 복원은 git revert다.
- 승인: 사용자 2026-11-24 「Yes, go ahead」 — 로컬 구현·검사·Draft PR. 병합(자동 배포)은 따로 묻는다.
