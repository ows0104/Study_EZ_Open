# 선행 문항 포함/미포함 선택 — 구현 계획

## 변경 범위·대상 파일·순서
1. `server/app/root_learning/planning.py`: `plan`/`plan_tasks`에 `prereqs` 인자, 끌어오기 범위(`reach`).
2. `server/app/root_learning/content.py`: `focus_for`가 prereqs도 읽는 `focus_prereqs` 추가.
3. `server/app/routes/root_learning.py`: focus 구역(RootFocus·save_focus·overview_data·refocus_stream·start 키)과
   mix 구역(MixStart·mix_start)만.
4. `server/app/root_learning/mix.py`: `select`에 선행 끌어오기.
5. 웹: `types/rootLearning.ts`, `RootToday.tsx`(토글), `RootLearning.tsx`(changeFocus 인자), `RootBatch.tsx`(체크·옵션 비교).
6. 검사: `server/tests/test_root_prereq_toggle.py`(새), 기존 focus·mix·existence 검사.

## 검사 명령과 성공 조건
- 서버: `server/`에서 `.venv/Scripts/python.exe -m tests root` 통과(새 검사 포함).
- 웹: `npm --prefix web run typecheck`, `npm --prefix web run build` 통과.
- 화면: 로컬 미리보기에서 토글·체크가 보이고 누를 수 있는지(가능한 범위).

## 위험·복원·승인할 범위
- 위험: 회차 ID 키가 바뀌면 오늘 진행 중 회차를 잃는다 → 기본값일 때 키를 바꾸지 않는다.
- 복원: git revert. DB 변경 없음.
- 승인: 사용자 요청 발언이 구현 승인. 운영 DB 쓰기·배포는 이 작업에 포함하지 않는다.
