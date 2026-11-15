# 빈칸 묶음 선지에서 정답에만 붙은 항목 머리 떼기 — 구현 계획

## 변경 범위·대상 파일·순서
`studyez_contracts/roots/mcq.py`(`_cloze_values`, `groups` cloze 한 줄), `tests/quizbank/test_root_mcq.py`(새 검사 하나).

## 검사 명령과 성공 조건
- `python -m pytest tests/quizbank tests/contracts` 통과.
- 선지 관련 `tests/quizbank/test_root_mcq.py`·`tests/runner/*root_mcq*`·`*root_choices*`·`*root_front*` 등 통과.
- `server/`에서 `PYTHONPATH=.. .venv/Scripts/python.exe -m tests mcq` 통과.
- 로컬 `runs/_root-generation/*/mcq/auto-*.json` 전부 `validate_v2` 통과.

## 위험·복원·승인할 범위
머리가 실제로 값의 일부인 답이 잘릴 수 있다 — 머리가 빈칸 밖 발문에 있고 글자를 품을 때만 떼어 줄였다. 복원은 커밋 revert.
사용자의 작업 요청이 구현 승인이다. master 병합(=API 자동 배포)은 사람 승인.
