# Main-Quiz 존재 선행: 목표 단위 대신 문항 단위로 끌어오기 — 구현 계획

## 변경 범위·대상 파일·순서
1. `server/app/root_learning/planning.py`: `existence_links(doc, records)`(R1), `plan`·`plan_tasks`의 `links` 인자와 문항 단위 끌어오기(R2).
2. `server/app/root_learning/content.py`: `existence_links(db, row)`(R3, 판별 메모리).
3. `server/app/routes/root_learning.py`: `planning.plan` 호출 세 곳에 `links=`.
4. `server/tests/test_root_existence_links.py`(새): spec 수용 항목.
5. 운영 사본 재현: 읽기 전용 조회 → 로컬 계산, 결과를 release.md에.

## 검사 명령과 성공 조건
- `server/.venv/Scripts/python.exe -m tests root_` (PYTHONPATH=..로 이 worktree의 studyez_contracts): 전부 통과.
- 서버 전체 `server/.venv/Scripts/python.exe -m tests`: master와 같은 결과.
- 재현: 261110_02 오늘 학습자 기준 Q107 없음, 끌려온 Optional은 전제를 답하는 문항뿐.

## 위험·복원·승인할 범위
- 위험: 존재 목표의 다른 과제가 오늘 목록에서 빠져 학습 순서가 달라진다(의도). 기록 읽기 실패 시 None → 지금 동작.
- 복원: `git revert` 뒤 재배포.
- 승인: 사용자 「응, 고쳐줘」(2026-11-18). 코드 배포(master 병합)는 되돌릴 수 있는 배포. DB·판·학습 기록 변경 없음.
