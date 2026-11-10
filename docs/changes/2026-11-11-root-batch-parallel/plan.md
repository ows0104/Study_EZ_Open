# Main-Quiz 생성 검수·수정 묶음 병렬화 — 구현 계획

## 변경 범위·대상 파일·순서
1. `connection_visuals.py` 잠금(R7).
2. `connection_generate_v3.py` Stages: RLock, `run(..., material=None)`, `canonical(names)` 단계 순서 정리,
   새 ledger에 `batchMode`. `parallel_calls()` 도구(최대 3, 실패 모아 첫 것을 올림).
3. 공용 묶음 실행기 `quizbank/connection_batches.py`: 시작 사본, 결합 검사(R4), 묶음별 material,
   합치기(R3), 중복 짝 재확인 대상 계산(R6). v3·v4가 묶음 본문(버전별 함수)을 넘긴다.
4. v3·v4 run의 4단계를 묶음 본문 함수로 바꾸고 순차/병렬을 실행기가 고른다. 순차 경로는 지금과 같은 입력.
5. R8 첫 커버리지·지도 점검, 의학 묶음 동시 실행.
6. 계약 `check_conflict_scope`, 지시문 문단(R5).
7. 검사 `tests/quizbank/test_root_batch_parallel.py`.

## 검사 명령과 성공 조건
- `python -m pytest tests/quizbank/test_root_batch_parallel.py -q`
- `python -m pytest tests/quizbank tests/contracts -q` (기존 회귀)
- `python -m pytest tests/runner -q`
- `python -m ruff check --select F821,F841 quizbank studyez_contracts runner` (개명 뒤 F821)
성공: 새 검사 전부, 기존 검사는 이 변경 전과 같은 결과.

## 위험·복원·승인할 범위
- 위험: 묶음이 다른 묶음의 수정을 못 본다 → R4로 결합 강의는 순차. 동시 호출 제한 → 최대 3(러너 기존 선례).
- 복원: 병합 되돌리기와 러너 이전 설치본으로 복귀. 새 ledger만 병렬이라 기존 실행에 영향 없음.
- 승인 범위(「계획대로 진행」): 브랜치 코드·지시문·검사, 로컬 검사, PR.
  실제 모델 재생·master 병합·러너 재설치는 별도(병합·설치는 /4 로컬 시범 뒤).
