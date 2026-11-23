# /4 Codex 단계 시한 3600초 — 구현 계획

## 변경 범위·대상 파일·순서
1. `runner/root_native_json.py` 상수 한 줄과 기본값 한 줄.
2. `tests/runner/test_root_claude_provider.py` 기대값 한 줄.
3. 병합 뒤 러너 `.runtime` 재설치. job 728 재실행은 사용자 확인 뒤 별도로.

## 검사 명령과 성공 조건
- `python -m pytest tests/runner tests/quizbank` — 시한 검사 통과, 나머지 회귀 없음.

## 위험·복원·승인할 범위
- 위험: 정말 멈춘 Codex 단계를 20분 더 기다린다. 편 전체 시한 180분이 상한으로 남는다.
- 복원: 상수를 2400으로 되돌리고 러너 재설치.
- 승인 범위: 위 두 파일과 이 폴더, 로컬 검사·PR. 병합·러너 재설치·재출제는 따로.
