# Main-Quiz 풀이 중 내 중요도 변경 — 구현 계획

## 변경 범위·대상 파일·순서
1. 서버 `server/app/root_learning/policy.py`(tier 목표·factor), `state.py`(개인 중요도 읽기·예정일 재계산),
   `content.py`(앞면 tier·개인 적용·tier 사건 조회), `server/app/routes/root_learning.py`(PUT 경로, 세션·prepare·문제 수정 응답에 적용),
   `server/app/usage_actions.py`·`routes/usage.py`(root_tier).
2. 검사 `server/tests/test_root_tier.py`(신규), `test_route_contract.py`, `test_root_usage.py`.
3. 웹 `web/src/bank/RootSolve.tsx`(내 중요도 선택·원래대로·안내), `RootLearning.tsx`(경로·응답 반영), `web/tests/root-learning.*`.

## 검사 명령과 성공 조건
- `server/.venv/Scripts/python.exe -m tests` 전체 통과(격리 SQLite, `PYTHONPATH`=이 worktree).
- `python scripts/check_root_learning.py --check root-ui` 통과.
- `npm --prefix web run typecheck`, `npm --prefix web run build` 통과.
- 로컬 fixture 브라우저에서 중요도 변경·원래대로·새로고침 유지 확인.

## 위험·복원·승인할 범위
- 위험: 개인 중요도가 복습 간격을 크게 늘릴 수 있다(Core→Optional 약 4.6배). 시험 상한·365일 상한은 그대로 적용된다.
- 복원: git revert 후 master 자동 배포, 또는 이전 Cloud Run revision·Pages. 추가된 `tier` 사건은 옛 코드가 무시한다.
- 승인: 사용자 작업 요청(intent.md 원문)이 구현·되돌릴 수 있는 코드 배포 근거다. DB 스키마 변경·학습 기록 변경 없음.
