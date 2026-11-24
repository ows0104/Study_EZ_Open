# 러너 첫 쓸기 켠 뒤 30초 — 구현 계획

## 변경 범위·대상 파일·순서
1. `runner/agent.py`: `FIRST_SWEEP_SECONDS = 30`, `sweep_loop` 첫 대기, 모듈 설명 한 줄.
2. `tests/runner/test_agent_parallel.py`: 첫 쓸기는 곧 돌고 두 번째는 원래 간격을 기다리는 검사.

## 검사 명령과 성공 조건
- `python -m pytest tests/runner -q` 통과(바로가기 설치 검사 1개는 worktree에 `.venv`가 없어 실패하는 환경 문제).

## 위험·복원·승인할 범위
- 위험: 켤 때마다 30초 뒤 쓸기 한 번(약 3분)이 더 돈다. 켜자마자 일감과 쓸기가 겹치는 것은 지금도 10분 뒤에 겹치는 것과 같다.
- 복원: git revert 후 러너 재설치.
- 승인: 사용자 2026-11-24 요청. 로컬 구현·검사·Draft PR까지. 병합·러너 재설치는 따로 묻는다.
