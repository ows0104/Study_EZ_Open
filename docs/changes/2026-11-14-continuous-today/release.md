# Main-Quiz 오늘 학습 이어 풀기 — 배포 준비

## 코드 리뷰·검증 결과

- server 전체: `python -m tests` 152개 중 150개 통과(격리 SQLite). 실패 2개 `test_root_map_tree`·`_v3`는
  quizbank가 `fitz`(PyMuPDF)를 import하지 못한 것이다. 검사에 쓴 메인 체크아웃 server venv에 PyMuPDF가 없다.
  이번 변경과 무관한 환경 문제다(11-12 tier-filter release.md와 같은 원인). 기록: state.json `server`.
- 새 검사(`test_root_focus`): 칩을 바꿔도 같은 세션. 푼 Q1·답을 연 Q2·번호 유지. Optional 끄고 켜면 원래 목록과 같음.
  Z가 앞부분으로 돌아감. 끝에서 칩을 줄이면 끝났다가 다시 켜면 Q3이 같은 흐름으로 돌아옴.
  끝난 흐름에 붙일 것이 없으면 409. 버전 경합은 409.
  더 풀기: 끝난 흐름 뒤에 붙고 번호가 이어지며(`extraGoals`=1), 그 뒤 칩을 바꿔도 붙인 목표가 유지됨.
  `test_root_planning`에 `new_goals` 검사 추가.
- web: `npm run build`(타입 검사 포함) 통과. 처음 기록은 종료 2였다. prepare-prompts가 `bank-prompt.json`을 LF로 다시 써서
  지문이 바뀐 것이고, 빌드는 성공했다. 되돌린 뒤 다시 기록해 0.
- 브라우저 회귀: `scripts/check_main_quiz_ui.py browser`(격리 fixture) `root-learning.test.cjs` 9/9 통과.
- 브라우저 수동(격리 fixture API + vite, `web/tests/root-learning.html`, Q3을 Optional로 둠): 1번을 푼 뒤 시작 화면으로 갔다.
  Optional을 끄면 배지 2→1, 켜면 2로 돌아왔고 버튼은 계속 「오늘 학습 재개」. 재개하니 「문항 2 / 3」.
  다 푼 뒤 버튼은 「더 풀기」. 이 fixture는 남은 과제가 없어 비활성이다. 붙이는 동작은 서버 검사로 확인했다. 콘솔 오류 없음.
- 설계 중 바꾼 점(spec R2): 처음 계획은 「뒷부분의 미학습 새 목표 수」로 새 목표 몫을 묶는 것이었다.
  그러면 칩을 껐다 켤 때 목표가 빠지는 경우가 있었다(fixture로 확인). 그래서 「오늘 처음부터 이 칩이었다면」의 계획으로 바꿨다.
  오늘 푼·연·넘긴 기록을 뺀 상태로 계획하고, 오늘 건드린 과제를 뺀다.
- 리뷰: 풀이 화면(RootSolve.tsx, #162 진행 중)은 건드리지 않았다. 평가·되돌리기·제외 이벤트, 요약·진척 분모는 그대로다.
  새 경로는 없다(route_contract 통과).

## 배포 대상 버전·순서·데이터 변경

- master 병합 → 일반 자동 배포(API 먼저, 같은 SHA의 웹). DB 스키마·migration 없음.
- 데이터: 칩을 바꾸거나 더 풀기를 누를 때 오늘 `root_session`의 `tasks`(뒷부분)·`version`이 바뀐다.
  더 풀기를 누르면 `state.extraGoals`도 바뀐다. 이벤트·기록은 지우지 않는다.

## 배포 후 확인·롤백·필요한 사람 승인

- 확인: 운영 Main-Quiz에서 몇 문항 푼 뒤 칩을 껐다 켜기 → 「오늘 학습 재개」가 같은 번호에서 이어지는지 본다.
  목록을 다 풀면 「더 풀기」가 나오는지 본다.
- 롤백: `git revert` PR. 길어진 세션 tasks는 옛 코드도 그대로 읽는다.
- 승인: 구현·Draft PR은 사용자 2026-11-14 「승인, 구현해」. master 병합(=배포)은 별도 승인 필요.
