# Main-Quiz 개념 지도 가지 보기 — 배포 준비

## 코드 리뷰·검증 결과

### 변경
- `rootMapTree.ts`
  - 왼→오 `layout`·`SIZE`를 지웠다.
  - 새로 넣은 함수는 셋이다.
    - `lanes`: 최상위 주제마다 열 하나, 하위 주제를 깊이 순서로 낸다.
    - `questionsOf`
    - `lanesPerRow`: 8열을 넘으면 줄을 감싼다.
  - `buildTree` 규칙은 그대로다.
- `RootMap.tsx`
  - 강의 카드 → 열 머리 → 들여쓴 주제 줄을 HTML로 그린다.
  - 문항은 상태 점이다. 주제를 누르면 문항 줄·계통 강조·연결선·패널이 나온다.
  - 가지선·연결선은 SVG 겹침층에 그린다.
  - 760px 미만은 세로 목록이다.
  - 연결선 설명은 판 관계의 `condition`(뜻)을 쓰고, 없으면 `reason`을 쓴다.
  - 확대·이동·키보드·찾기·패널·목록 보기는 유지했다.
- `main-quiz.css`
  - 옛 SVG 노드 규칙 21줄을 지우고 열 스타일을 더했다.
  - Main-Quiz 지도 화면에서만 콘텐츠 폭 제한(1100px)을 푼다(`:has(.main-quiz-map)`).
  - 지도 틀 높이는 `max(560px, 100dvh − 230px)`이다.
- 검사 파일
  - `main-quiz-map-tree.test.cjs`: lanes·lanesPerRow 단언.
  - `root-learning.test.cjs`: 첫 화면에 모든 노드가 틀 안에 있고 배율이 0.6 이상인지, 펼침/접힘, 「문항 펼치기」, 확대 시 transform 변화를 본다.

### 검사(`scripts/development.py verify`, 로그 `runs/_development/2026-11-09-main-quiz-lane-map/`)
- `npm --prefix web run typecheck`: 0
- `node --test web/tests/main-quiz-map-tree.test.cjs`: 4/4
- root-ui 브라우저 검사: `root-learning.test.cjs` 4/4와 단위 검사 4/4, 모두 8/8 통과.
  - 격리 fixture API(SQLite·로컬 저장소, `tests.serve_main_quiz_ui_fixture`)와 vite를 썼다.
  - 이 worktree에 server venv가 없어서 `scripts/check_root_learning.py --check root-ui`와 같은 단계를 메인 checkout의 server venv와 `PYTHONPATH=<worktree>`로 실행했다.
- `npm --prefix web run build`: 0
  - 첫 기록 실행은 끝에 「✓ built」가 찍혔는데도 종료 코드 2였다.
  - 직접 실행과 재기록 실행은 모두 0이었다. 원인은 재현되지 않았다.

### 실제 데이터 확인
감염병리1 map-tree-26110803 지도 응답(review concepts·relations·targets)을 fixture 지도 경로에 넣어 확인했다.
- 1600×900 첫 화면: 가지 7, 주제 62, 노드 64개가 모두 틀 안에 있고 배율은 0.66이다. 콘솔 오류는 0이다.
- 「결핵」 선택: 문항 3줄, 사르코이드증·크론병까지 연결선이 그려지고 패널이 열린다.
- 「연결선 전체」로 연결선이 모두 그려진다.
- 390×844에서 가로 넘침이 없다.

### 남은 것
- `web/src/notices/GuidePage.tsx`의 개념 지도 안내는 옛 동작(「모두 펼치기」, 주제를 눌러 문항 펼침)을 설명한다.
  - 이 파일은 진행 중인 UI 개편 작업(claude/redesign-1107-feedback) 범위라 여기서 고치지 않았다. 후속으로 남긴다.
- 문항을 품지 않는 말단 개념(예: 항산염색 AFB)은 지금처럼 지도 노드가 아니다(`buildTree` 규칙 유지).

## 배포 대상 버전·순서·데이터 변경
- 대상은 이 브랜치(claude/main-quiz-lane-map)의 PR 병합 커밋이다.
- master 병합 → GitHub 검사 → API(변경 없음, 같은 SHA로 재배포) → Pages 순서다.
- 서버·DB·판·학습 기록·공개 범위 변경은 없다. 「사람에게 묻는 것」에 닿지 않는다.

## 배포 후 확인·롤백·필요한 사람 승인
- 확인할 것
  - master 실행의 검사·배포가 성공했는지
  - `/api/health` SHA
  - Pages가 새 RootLearning 청크와 `mq-lanes` CSS를 내는지
- 롤백: 병합 커밋 revert를 push한다(자동 재배포). 필요하면 이전 Pages 배포로 되돌린다.
- 승인: 사용자 작업 요청(2026-11-09 「가지 보기로」)이다. 개발 루프 2026-11-08에 따라 코드 배포는 따로 묻지 않는다.
