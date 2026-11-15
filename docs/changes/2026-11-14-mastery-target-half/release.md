# 검증

- 서버 `score`·`plan`·`mastery`·`timetable`·`light`·`optional`·`test_root_state`·`test_root_api`·`test_root_question_progress` 전부 통과.
  앞선 `-m tests root` 실행에서 실패 2개(`test_root_map_tree`, `test_root_map_tree_v3`)는 서버 venv에 `fitz`(PyMuPDF)가 없는 환경 문제.
- 전체 서버 검사는 로컬에서 10분 안에 끝나지 않아 PR CI에 맡긴다.
- 웹 `npx tsc -b --noEmit` 통과(이 worktree에서 `npm ci`).
- `shownGoal` 수치 확인(목표 4%p): 안 함 → 목표 2·남음 2·0%, 1 확보 → 남음 1·50%, 2 확보 → 완료 100%, 목표 0 → 완료.
- 미확인: 운영 화면에서의 실제 값(로컬 서버는 운영 DB를 가리켜 띄우지 않았다).
