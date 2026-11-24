# Codex 기본 모델 gpt-6.2-sol — 구현 계획

## 변경 범위·대상 파일·순서
1. `studyez_llm/codex.py` `DEFAULT_MODEL`.
2. 도움말: `runner/cli/arguments.py`, `quizgen/run.py`, `quizgen/reproduce.py`. 문서: `docs/quizgen.md`, `docs/pipeline.md`.
3. 검사: `tests/studyez_llm/test_codex.py`에 기본값 검사 하나. 다른 검사의 `gpt-6.1-sol`은 임의 이름이라 그대로 둔다.
4. 실제 호출 하나(러너 CLI).

## 검사 명령과 성공 조건
- `python -m pytest tests/quizbank tests/runner tests/studyez_llm tests/contracts -q` — 회귀 없음.

## 위험·복원·승인할 범위
- 위험: 모든 Codex 출제·검수의 모델이 바뀐다. 속도·출력 길이·품질이 달라질 수 있다.
- 복원: 러너 PC에 `STUDYEZ_MODEL=gpt-6.1-sol`, 또는 이 PR revert 후 재설치.
- 승인 범위: 위 파일과 이 폴더, 로컬 검사·실제 호출·PR·병합·러너 재설치(사용자 「어 고치고 병합후 재설치해줘」).
