# Main-Quiz 보충 포인트 ID 충돌 수정 — 구현 계획

## 변경 범위·대상 파일·순서
1. `studyez_contracts/roots/generation_v3.py` `attach_points`에 `reserved` 인자.
2. `studyez_contracts/roots/generation_v4.py` `attach_points` 전달.
3. `quizbank/connection_generate_v3.py`·`connection_generate_v4.py` 호출에 brief 포인트 ID 전달.
4. 검사: `tests/contracts/test_generation_v3.py`·`test_generation_v4.py`에 brief 전용 포인트와 겹치지 않는 번호 테스트.

## 검사 명령과 성공 조건
- `python -m pytest tests/contracts -q` 통과.
- 261113_02 실제 산출물(points 87, brief 93, supplement Q092)로 새 코드의 attach_points → extend_brief가 P094로 통과하는지 로컬 재현.
- PR CI `Tests and build`, `Windows runner checks` 통과.

## 위험·복원·승인할 범위
- 위험: 낮음. 기본값이 기존 동작. 번호만 바뀌고 내용·tier 계산은 같다.
- 복원: PR revert.
- 승인 범위: 위 파일의 로컬 구현·검사·Draft PR까지. master 병합(=자동 배포)과 러너 재설치·261113_02 재실행은 따로 묻는다.
