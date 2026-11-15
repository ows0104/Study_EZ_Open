# 개인 수정한 Main-Quiz 문항의 선지 유지 — 구현 계획

## 변경 범위·대상 파일·순서
`server/app/root_learning/mcq.py`(짝 찾기), `server/tests/test_main_quiz_mcq_choices.py`(회귀 검사).

## 검사 명령과 성공 조건
`server/`에서 `.venv/Scripts/python.exe -m tests root main_quiz route_contract` 전부 통과. 새 절은 수정 전 코드에서 실패(KeyError: mcq_choices)함을 확인했다.

## 위험·복원·승인할 범위
고친 단답 정답이 원래 오답과 뜻이 같으면 오답이 정답처럼 보일 수 있다 — 같은 글은 빼지만 뜻 비교는 하지 않는다. 복원은 커밋 revert.
