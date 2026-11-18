# Main-Quiz 모아풀기 — 출시 메모

## 바뀐 것
- 강의 목록(`/study`): Main-Quiz가 열린 강의에 체크가 다시 생긴다. 체크하면 아래 막대 「n개 강의 선택 · 오늘 복습 n장 · 모아풀기」.
- 「모아풀기」 → 새 화면 `/study/mix?l=<과목>/<runId>&…`
  - 시작 화면: 강의별 「오늘 n문항」/「남은 n문항」/「오늘 목록 마침」/「오늘 과제 없음」/「열 수 없음」, 주관식·객관식, 「모아풀기 시작」(이어 풀 회차가 있으면 「재개」).
  - 풀이: 기존 Main-Quiz 풀이 화면 그대로. 제목 줄은 지금 문항의 강의, 진행은 전체 합. 강의는 남은 비율이 큰 쪽부터 번갈아 나온다.
  - Z: 강의를 건너 방금 한 행동부터 거꾸로.
  - 마침: 강의별 문항 수·첫 학습·회상 가능.
- 서버·DB·프롬프트·생성기 변경 없음. 학습 이벤트는 강의 하나로 풀 때와 같은 강의별 회차에 쌓인다.

## 검사 (2026-11-18, worktree feat/main-quiz-batch)
- `npm --prefix web run typecheck` 통과. `development.py verify --check web` 기록.
- `npm --prefix web run build` 통과.
- `python scripts/check_root_learning.py --check root-batch` 통과(새): 격리 sqlite 합성 두 강의 + 없는 강의 하나.
  섞기 순서 A1→B1→A2…, 강의를 건넌 Z 두 번(평가·답 보기), 새로고침 뒤 「남은 2문항」 재개, 마침 화면의 강의별 결과,
  마침 화면 Z, 회차 2개·평가 8·되돌리기 3 이벤트, 390px 가로 넘침 없음, 페이지 오류 0.
- `python scripts/check_root_learning.py --check root-ui` 9개 통과(강의 하나 Main-Quiz 회귀 없음).
- `node --test web/tests/study-mix-pick.test.cjs` 통과(새): 목록 체크 → 막대 → 고른 강의를 목록 순서로 실은 주소.
- 미통과(기존): `web/tests/study-management.test.cjs`는 76행 「퀴즈 없음」 문구를 기다리다 실패한다.
  master에도 그 문구를 그리는 코드가 없다(11-06 이후 고쳐지지 않은 검사). 이번 변경과 무관해 고치지 않았다.
- worktree에 `server/.venv`가 없어 검사 스크립트에 `STUDYEZ_SERVER_PYTHON`(메인 체크아웃 venv)을 줄 수 있게 했다. PYTHONPATH는 worktree라 계약은 이쪽 것이다.

## 남은 위험
- 한 쓰기 줄로 여러 회차를 보내므로 한 강의의 409가 그 뒤 요청을 모두 보존·정지시킨다(강의 화면과 같은 보존 규칙, 기록 손실 없음).
- 화면을 새로고침하면 Z 스택이 비어 새로고침 전 행동은 Z로 못 돌린다(강의 화면은 서버 스택으로 돌린다). 필요하면 다음 작업.
- 관리자 「선택 강의 누락 검증·객관식 보강」(Quiz Bank 검수 요청)이 체크로 다시 닿는다. 11-11 전과 같은 관리자 전용 도구다.
- 모아풀기 화면에는 개념 지도·중요도 칩·「더 풀기」가 없다(강의 하나 화면에 있다).

## 되돌리기
웹만 바뀐다. git revert 뒤 Pages 재배포.
