# Codex 기본 모델 gpt-6.2-sol — 배포 준비

## 코드 리뷰·검증 결과
- 변경: `studyez_llm/codex.py` `DEFAULT_MODEL` 한 줄, 도움말 세 줄, 문서 두 곳, 기본값 검사 하나.
- 검사: `python -m pytest tests/quizbank tests/runner tests/studyez_llm tests/contracts -q`(development.py verify regression, 결과는 state.json).
  바로가기 설치 검사 하나는 worktree에 `.venv`가 없어 뺐다(앞 두 변경과 같다).
- 실제 호출(2026-11-24, 러너 PC, CLI 0.167.0-alpha.3.2, 공급자 studyez): `gpt-6.2-sol` 짧은 호출 6.1초 정상.

## 배포 대상 버전·순서·데이터 변경
- 러너 PC 코드만 바뀐다. 서버·웹·DB·계약·지시문 변경 없음. master 병합이 API·웹을 다시 배포하지만 내용은 같다.
- 병합 뒤 러너 `.runtime` 재설치. 도는 일감이 없을 때 바꾼다.

## 배포 후 확인·롤백·필요한 사람 승인
- 확인: 재설치한 러너에서 `codex.model_name()`이 `gpt-6.2-sol`. 첫 출제의 단계 기록 `model`과 `~/.codex/sessions` rollout의 모델.
- 롤백: 러너 PC에 `STUDYEZ_MODEL=gpt-6.1-sol`(코드 그대로), 또는 이 PR revert 후 재설치.
- 사람 승인: 병합·재설치는 사용자 「어 고치고 병합후 재설치해줘」.
