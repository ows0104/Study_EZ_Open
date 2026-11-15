# Main-Quiz 선행: 끌어오기·막기는 문항 사이 선행만 — 구현 계획

승인: 사용자 「1+2+3 다 고치기」(2026-11-15), 「응 그 방향으로 진행해줘」(2026-11-16). master 병합(=배포)은 따로 확인.

## 변경 범위·대상 파일·순서

1. `studyez_contracts/roots/generation_v2.py`: `question_dependencies` 추가, `order_plan` 따라가기 규칙(spec R1·R2·R3).
2. `tests/contracts/test_generation_v2.py`: 목표 선행 순서만·끌어오지 않음, 준비 안 된 선행 건너뜀.
3. `server/app/root_learning/content.py`: `close_prerequisites` 삭제, 두 분기 모두 자기 이유만.
4. `server/app/root_learning/planning.py`: 후보 안 「명시적 선행 연결」 유지(spec R1). master(#190) 병합 뒤 필터 밖 끌어오기는
   존재 목표 간선만(spec R1a, `studyez_contracts/roots/presuppose.py`의 `is_existence_edge`). `server/tests/test_root_prereq_release.py` 갱신.
5. `server/app/routes/root_learning.py`: `project_session`·`prepare`에 `prerequisite`.
6. `server/tests/test_root_prereq_closure.py`: 새 규칙으로 갱신.
7. `web/src/types/rootLearning.ts`, `web/src/bank/RootSolve.tsx`, `web/src/bank/RootLearning.tsx`(프레임→화면 복사): 「선행 문항」 태그.

## 검사 명령과 성공 조건

- 루트: `python -m pytest tests/contracts`(anaconda) 통과.
- `server/`: `PYTHONPATH=.. .venv/Scripts/python.exe -m tests root`, `-m tests main_quiz`, `-m tests route_contract` 통과(격리 SQLite).
- 웹: `npm --prefix web run typecheck`.
- 운영 사본 재현(읽기 전용 조회 → 로컬 계산, 쓰기 없음): 레지오넬라 Essential만 계획과 막힌 과제 수.

## 위험·복원·승인할 범위

- 위험: 고른 중요도 밖의 앞 목표는 더 이상 당겨 오지 않는다(#190·#194 존재 목표 포함). 고른 중요도 안에서는 그대로 당겨 오고 순서도 남는다.
- 위험: 선행을 제외한 학습자가 선행 없이 뒤 과제를 본다(사용자 결정 2번).
- 복원: `git revert`. 데이터 변경 없음.
- 범위: 위 파일 로컬 구현·검사·Draft PR.
