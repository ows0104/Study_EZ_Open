# 접수 단계의 출처 충돌 인용 누락을 경고로 — 구현 계획

## 변경 범위·대상 파일·순서
1. `quizbank/connection_generate_v3.py`: `_CONFLICT_GAP`, `intake_rejections`, `_intake`가 이를 사용.
2. `quizbank/connection_generate_v4.py`: `_intake`가 같은 함수를 사용.
3. `tests/quizbank/test_intake_conflict_gap.py`: 인용 누락은 진행, 다른 은행 오류는 정지, 문항 오류는 그 문항만.
4. 261111_02 packet(runs/_root-generation/cf4d5917…/generation/packet.json)으로 접수 검사를 재현한다.

## 검사 명령과 성공 조건
- `python -m pytest tests/contracts tests/quizbank -q`: 전부 통과.

## 위험·복원·승인할 범위
- 승인 범위: 위 구현, 로컬 검사, PR. 병합하면 배포되고, 러너 재설치와 261111_02 재요청이 뒤따른다.
- 위험: 인용이 빠진 충돌 기록이 게시까지 갈 수 있다. 결과 `validation.errors`와 관리자 issue로 보인다.
- 복원: 커밋 되돌림. 데이터 변경 없음.
