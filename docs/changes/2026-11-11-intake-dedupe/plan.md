# 생성기 시작 단계의 반복 값 자동 정리 — 구현 계획

## 변경 범위·대상 파일·순서
1. `studyez_contracts/roots/generation_v3.py` `intake_projection`: spec 표의 다섯 정리를 schema_version·importance 정리 앞에 둔다.
2. `tests/contracts/test_generation_v3.py`: 정리 다섯 경우, 내용이 다른 중복 계획, 반복 없는 은행.
3. 261102_02 /3 결과(runs/_root-generation/1c484a7b…)의 intakeProjection이 새 함수로도 같은지 확인한다.

## 검사 명령과 성공 조건
- `python -m pytest tests/contracts tests/quizbank -q`: 전부 통과.
- `bank-prompt.json`이 바뀌었으면 `git restore`.

## 위험·복원·승인할 범위
- 승인 범위: 위 파일의 구현, 로컬 검사, PR 생성. 병합(=배포)과 러너 재설치는 따로 묻는다.
- 위험: 생성 시간 단축 세션과 같은 파일. 함수가 달라 충돌 가능성은 낮고, 충돌하면 나중에 병합하는 쪽이 푼다.
- 복원: 커밋 되돌림. 데이터 변경 없음.
