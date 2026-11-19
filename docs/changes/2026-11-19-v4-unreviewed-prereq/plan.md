# Main-Quiz /4 조립: 검토가 확인하지 않은 선행 연결을 투영에서 뺀다 — 구현 계획

## 변경 범위·대상 파일·순서
1. `studyez_contracts/roots/generation_v4.py` `_compile`: 투영 선행 연결 거르기(R1).
2. `tests/contracts/test_generation_v4.py`: 목표 둘과 선행 연결 하나.
   - `unknown`이면 빠지고 조립이 끝난다.
   - `supported`면 남는다.
3. job 700 사본 재생: 모델 호출 없이 결과, validate_all, completed_result, validate_result까지 간다.
4. PR(Draft→Ready 한 번) → 병합(API 자동 배포) → 러너 재설치 → job 700 이어 하기 요청 하나.

## 검사 명령과 성공 조건
- `python -m pytest tests/contracts tests/quizbank -q`: 모두 통과.
- 서버: `server/tests`의 root 생성 경로 검사. server venv에 `PYTHONPATH=..`를 둔다.
- `C:\sez\rp\a700_replay.py`: `REPLAY OK`.

## 위험·복원·승인할 범위
- 위험이 낮다. 지금 멈추는 경우만 달라진다.
- 복원은 git revert다.
- 승인: 사용자 「고쳐서 이어 해」. 운영 DB 쓰기는 job 700 이어 하기 요청 하나. 공개판 교체는 11-18 「교체한다」.
