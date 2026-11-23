# Main-Quiz 강의 문항 전체 보기 — 구현 계획

## 변경 범위·대상 파일·순서
1. 새 `server/app/root_learning/question_list.py` — 행·쪽 번호 계산.
2. `server/app/routes/root_learning.py` — 끝에 `GET …/questions`, `GET …/questions/{id}/detail`(새 구역, 다른 경로는 안 건드림).
3. 새 `server/tests/test_root_question_list.py` — 목록·개인 수정 반영·내 중요도 반영·읽기 전용·권한·404.
4. `web/src/types/rootLearning.ts` — 응답 타입. 새 `web/src/bank/RootQuestionList.tsx`, `web/src/bank/question-list.css`.
5. `web/src/App.tsx`(경로 한 줄), `web/src/bank/RootToday.tsx`(시작 화면 「전체 문항」 링크).
6. `web/src/notices/GuidePage.tsx`에 안내 한 줄(있으면).

## 검사 명령과 성공 조건
- 서버: `server/.venv/Scripts/python.exe -m tests root_question_list` 및 `-m tests root_personal`·`root_api` 통과.
- 웹: `npm run typecheck`, `npm run build` 통과.
- 로컬 화면: `tests/serve_root_fixture.py`(격리 DB·합성 자료)로 띄워 목록·검색·참고 쪽·수정 확인.

## 위험·복원·승인할 범위
- 읽기 전용 API와 새 화면만 더한다. 되돌리기는 git revert(코드 배포만).
- 목록 API가 한 판의 문항 전부를 보낸다(그림 제외, 판당 약 0.5 MB 사본 안). 그림은 상세에서만.
- 승인 범위: 위 파일의 로컬 구현·검사·Draft PR. 운영 DB 쓰기 없음.
