# Main-Quiz 조립 검사: cloze 답 단위 수·접수 탈락 번호 재사용 — 구현 계획

1. `generation_v4.py` 두 곳 수정(R1, R2).
2. 회귀: `pytest tests/contracts tests/quizbank tests/runner`.
3. 실패한 세 실행의 사본을 모델 호출을 막고 이어 해 조립 통과를 확인.
4. PR → 병합(API 자동 배포) → 도는 편이 끝난 틈에 러너 재설치 → 세 실행을 이유를 적어 이어 하기.

승인: 사용자 2026-11-12 일괄 출제 요청(「다시 러너해서 대기열 작업 진행하자」). 되돌릴 수 없는 작업 없음.
