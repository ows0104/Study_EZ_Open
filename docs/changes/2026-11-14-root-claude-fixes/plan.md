# Claude 출제 경로 보완 — 구현 계획

## 변경 범위·대상 파일·순서
1. `studyez_llm/claude.py`: 실제 모델 확인, 파일 입력, 제한 시간 배수.
2. `studyez_llm/execution.py`: `run_process(stdin=)`.
3. `quizbank/connection_generate_v3.py`: `_retire_other_model`.
4. 검사: `tests/studyez_llm/test_claude.py`, `tests/runner/test_root_claude_provider.py`.
5. 병합 → 러너 재설치 → `runs/model-overrides.json`의 261109_02 모델을 `claude-opus-5`로 → 관리자 재개.

## 검사 명령과 성공 조건
- 회귀 `pytest tests/contracts tests/quizbank tests/runner tests/studyez_llm` 전부 통과.
- 실제 CLI 연기 검사(강의 자료 없음): opus-5 이미지 읽기·실제 모델 기록, 10초×3 제한이 31초에 걸림(2026-11-14 확인).

## 위험·복원·승인할 범위
- 재개 때 다른 모델로 완료된 단계 4개(normalize·brief-fix·coverage-0-1·map-check-0)가 다시 돈다(시간·사용량).
- 롤백: PR revert. 승인: 사용자 「5로 쭉 이어서 가자.」(구현·배포·261109_02 재개).
