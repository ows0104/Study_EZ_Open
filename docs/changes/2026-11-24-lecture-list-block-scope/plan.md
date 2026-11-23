# 강의 목록 숫자 칸: 고른 블럭의 강의만 계산 — 구현 계획

## 변경 범위·대상 파일·순서
1. `server/app/routes/root_learning.py` `catalog`에 `lecture: list[str] = Query([])`를 더한다(R1–R3). 다른 함수는 건드리지 않는다.
2. `server/tests/test_root_catalog_scope.py`(새): R1–R3과 「묻지 않은 강의는 계산하지 않음」을 검사한다.
3. `web/src/bank/useRootCatalog.ts`: `useRootSummaries(keys)`로 바꾼다.
   - 키 집합마다 60초 캐시를 둔다.
   - 키가 바뀌는 동안은 `loaded: false`다(R5·R6).
   - `prefetchRootCatalog`를 뺀다.
4. `web/src/bank/StudyOverview.tsx`: 고른 블럭의 Main-Quiz 행의 키를 넘긴다(숨긴 행 포함, R4).
5. `web/src/bank/BankBatch.tsx`: prefetch 호출을 뺀다.

6. (더한 범위)
   - `server/app/root_learning/state.py` `question_progress`에 `newToday`를 더한다(R7).
   - `server/tests/test_root_question_progress.py`에 그 검사를 더한다.
7. `web/src/types/rootLearning.ts`·`StudyOverview.tsx`·`overview.css`: 「오늘 새 카드」 칸을 더한다(R8).
8. `web/src/bank/RootToday.tsx`: 시작 화면을 카드 기준으로 바꾼다(R9). 새 검사 화면은 `web/tests/root-today-cards.html|tsx`다.
9. 낡은 웹 검사 가운데, 이번 화면을 다루면서 master에서도 실패하던 것을 바로잡는다.
   - `study-loading`: 11-18부터 족보만 있는 칸이 행이 되어 11행이다.
   - `study-blocks`: 11-12에 바뀐 훅 이름 `useRootSummaries`를 가짜 모듈에 반영한다.

## 검사 명령과 성공 조건
- 서버: `server/`에서 `.venv/Scripts/python.exe -m tests root`(그리고 `card`·`mastery`).
  - 새 검사와 기존 root 검사가 통과한다.
  - `pymupdf`가 없는 환경의 map_tree 2개는 환경 탓이라 따로 적는다.
- 웹
  - `npm --prefix web run typecheck`가 통과한다.
  - 브라우저 검사 `study-loading`·`study-blocks`·`study-management`(vite 5197, Playwright)를 돌린다.
    - master에서도 실패하던 검사는 따로 적는다.
  - `tests/root-today-cards.html`은 ALL PASSED여야 한다.

## 위험·복원·승인할 범위
- 위험: 블럭을 바꿀 때 한 번 더 기다린다. 블럭 하나분이라 짧다.
- 복원: git revert와 이전 Cloud Run revision·Pages 배포.
- 승인: 사용자 2026-11-24 「응, 고쳐줘」. 위 파일·로컬 검사·Draft PR까지 한다.
  - 병합은 자동 배포라 따로 묻는다. 코드 배포는 되돌릴 수 있지만, 이 세션의 PR 습관을 따른다.
