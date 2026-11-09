# Main-Quiz 풀이 중 내 중요도 변경 — 구현 계획

## 변경 범위·대상 파일·순서
1. 서버 `server/app/root_learning/policy.py`(목표 기억률·숙련도·간격), `state.py`(개인 중요도 읽기·새 평가 목표 간격),
   `content.py`(앞면 tier·개인 적용·tier 사건 조회), `server/app/routes/root_learning.py`(PUT 경로, 세션·prepare·문제 수정 응답에 적용),
   `server/app/usage_actions.py`·`routes/usage.py`(root_tier).
2. 검사 `server/tests/test_root_tier.py`(신규: Quiz Bank `target_for`·`review_schedule`과 직접 대조), `test_main_quiz_four_ratings.py`
   (새 사건 roots-four-rating/2), `test_route_contract.py`.
3. 웹 `web/src/bank/RootSolve.tsx`(내 중요도 선택·원래대로·안내), `RootLearning.tsx`(경로·응답 반영), `web/tests/root-learning.*`.

## 검사 명령과 성공 조건
- `server/.venv/Scripts/python.exe -m tests` 전체 통과(격리 SQLite, `PYTHONPATH`=이 worktree).
- `python scripts/check_root_learning.py --check root-ui` 통과.
- `npm --prefix web run typecheck`, `npm --prefix web run build` 통과.
- 로컬 fixture 브라우저에서 중요도 변경·원래대로·새로고침 유지 확인.

## 위험·복원·승인할 범위
- 위험: 배포 뒤 첫 평가부터 간격 규칙이 바뀌어 학생의 Main-Quiz 복습량이 달라진다. Must-Know·Core는 숙련도가
  목표에 닿을 때까지 매일 다시 나올 수 있다. Optional은 빨리 뜸해진다. max_days 30·시험 상한은 그대로 적용된다.
- 복원: git revert 후 master 자동 배포, 또는 이전 Cloud Run revision·Pages. 추가된 `tier` 사건은 옛 코드가 무시한다.
- 승인: 사용자 작업 요청(intent.md 원문)이 구현·되돌릴 수 있는 코드 배포 근거다. DB 스키마 변경·학습 기록 변경 없음.
