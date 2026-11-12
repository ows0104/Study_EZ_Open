# Main-Quiz 오늘 학습 중요도 필터 — 배포 준비

## 코드 리뷰·검증 결과

- server: `python -m tests root main_quiz` 37개 통과(새 `test_root_focus` 포함, 격리 SQLite). 기록: state.json `server`.
  처음 실행에서 `test_root_map_tree`·`_v3` 2개가 실패했다. 새로 만든 worktree venv에 PyMuPDF가 없었던 환경 문제였고, 설치 뒤 통과했다. 코드 결함 아님.
- web: `npm run build` 통과(타입 검사 포함). 기록: state.json `web`.
- 브라우저: 격리 fixture API(`tests.serve_root_fixture`, 8027) + vite(5199)로 `web/tests/root-learning.html` 확인.
  Q3을 「내 중요도」 Optional로 두고 Optional 칩을 끄면 과제 3→2개. 새로고침 뒤에도 선택이 유지됐다. 시작한 회차는 「문항 1 / 2」.
  375px 폭에서 가로 스크롤과 콘솔 오류가 없었다.
- 2차(사용자 요청): 고른 칩에 체크 표시와 채운 배경을 넣었고, 「오늘 학습 시작」 버튼 안에 카드 수 배지를 추가했다.
  브라우저에서 Optional을 끄고 켜고 끄면 배지가 2→3→2로 바뀌었다. 데스크톱과 375px 모두 확인했다.
- 검증 중 찾은 결함(R8): 같은 시각에 저장한 focus 이벤트 중 「마지막」을 request ID 순으로 골라, 칩을 다시 켜도 반영되지 않을 수 있었다.
  `seq`로 순서를 정하도록 고쳤다. 역순 request ID로 회귀 검사를 추가했다(이전 코드에서는 실패하는 순서).
- CI 1차 실패: `test_route_contract`(경로 목록 고정 검사)에 새 `PUT …/focus`가 없어 실패(1/142). 목록에 추가해 로컬 통과.
  로컬 server 검사를 `root` 필터로만 돌려 이 파일을 놓쳤다.
- 미실행: Playwright 회귀 `web/tests/root-learning.test.cjs`(전용 5193 fixture 구성 필요). CI `Tests and build`가 실행한다.
- 리뷰: 선지 보기(#118)가 고치는 앞면·답면·prior_exposure·풀이 화면 스타일은 건드리지 않았다. 집계(replay·habitual·usage)는
  kind로 고르므로 focus 이벤트를 무시한다. 모두 선택이면 세션 ID·state가 그대로임을 테스트로 확인했다.

## 배포 대상 버전·순서·데이터 변경

- master 병합 → 일반 자동 배포(API 먼저, 같은 SHA의 웹). DB 스키마·migration 없음.
- 데이터: 사용자가 칩을 바꿀 때만 `root_event`에 kind='focus' 행이 추가된다. 기존 행은 바꾸지 않는다.

## 배포 후 확인·롤백·필요한 사람 승인

- 확인: 운영 Main-Quiz 강의 화면에서 칩 표시, 칩 토글 시 과제 수 변화.
- 롤백: `git revert` PR. 남은 focus 행은 이전 코드가 무시한다.
- 승인: 사용자 2026-11-12 「승인, 구현 시작」(plan.md 범위: PR·master 병합 포함).
