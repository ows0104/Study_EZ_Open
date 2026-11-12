# Main-Quiz 오늘 계획: 선행 과제가 빠진 과제를 plan에 넘기지 않기 — 구현 계획

## 변경 범위·대상 파일·순서

1. `server/tests/test_root_prereq_closure.py`(새): /4 standalone 판, Q4가 Q2를 선행으로. 고치기 전 실패 확인.
2. `server/app/root_learning/content.py`: 선행 닫힘을 `close_prerequisites`로 빼고 standalone 분기에도 적용.
3. `server/app/root_learning/planning.py`: `plan`·`plan_tasks`에 `focus=None` — 후보는 focus, order_plan 확인은 available.
4. `server/app/routes/root_learning.py`: `overview_data` 한 줄 — 좁힌 집합을 `focus=`로 넘긴다. catalog(#129 영역)는 건드리지 않는다.

## 검사 명령과 성공 조건

- `server/`에서 `PYTHONPATH=.. .venv/Scripts/python.exe -m tests prereq_closure`: 고치기 전 실패, 뒤 통과.
- 같은 방식으로 `-m tests root`, `-m tests main_quiz`, `-m tests route_contract` 전부 통과(격리 SQLite, server/.env 운영 DB 미사용).

## 위험·복원·승인할 범위

- 위험: 선행을 제외한 학습자에게 의존 과제가 오늘 목록·준비 수에서 빠진다(R1, 기존 규칙과 같음).
- 위험: 필터를 좁힌 학습자에게 고르지 않은 중요도의 선행 과제가 나온다(R2, 「명시적 선행 문항」 표시).
- 복원: `git revert`. 데이터 변경이 없다.
- 범위: 위 파일의 로컬 구현·검사, Draft PR. master 병합(=배포)은 사용자 확인 뒤.
