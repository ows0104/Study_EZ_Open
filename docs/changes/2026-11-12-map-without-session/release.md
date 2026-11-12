# Main-Quiz 개념 지도 회차 분리 — 배포 준비

## 코드 리뷰·검증 결과
- 서버 `-m tests root_`: 41개 파일 전부 통과(새 `test_root_lecture_map` 포함: 목록 완료 뒤 지도 200·회차 미생성,
  같은 날 반복 열람 기록 1건, 열람 뒤 새 회차 `mapSeen=True`, 다른 학습자·열람 없는 날은 False, 미공개 404, 요청 형식 422).
- 웹 `npm run build`·`tsc -b` 통과.
- Playwright `web/tests/root-learning.test.cjs`(격리 fixture API 8027 + vite 5193):
  「map from start」 통과 — 시작 화면에서 지도가 회차 시작 요청(POST sessions) 없이 열리고, 지도 틀이 화면을 꽉 채우며,
  「← 오늘」로 돌아가 「오늘 학습 시작」이 회차를 1번 연다.
- 기존 결함(이 변경과 무관): 같은 파일의 4개 테스트(actual API, toggles, Z undo, quiz timer)가
  `getByRole('button',{name:'오늘 학습 시작',exact:true})`를 못 찾아 실패. 이 변경을 뺀 master 웹 코드로 같은 fixture에서 돌려도
  같은 4개가 같은 이유로 실패함을 확인(시작 버튼 이름에 오늘 과제 수가 붙음). 따로 고친다.
- `map_view` 행은 `usage`의 마지막 활동 시각에만 반영(`_root_field`는 모르는 kind를 세지 않음). `focus`와 같은 취급.

## 배포 대상 버전·순서·데이터 변경
- DB 스키마 변경 없음. 새 행 종류 `RootEvent.kind='map_view'`(session_id '')만 추가.
- 서버(새 route) → 웹 순서. 웹만 먼저 나가면 회차 없는 지도 요청이 404 → 오류 배너(쓰기 큐는 막히지 않음).

## 배포 후 확인·롤백·필요한 사람 승인
- 확인: 오늘 과제 0개 강의에서 「개념 지도」 → 지도 표시, 충돌 배너 없음.
- 롤백: `git revert`. `map_view` 행은 집계에 쓰이지 않아 남아도 무해.
- 기존 브라우저에 보관된 충돌 응답은 사용자가 「보관 응답 확인 후 서버 기록 불러오기」를 한 번 눌러야 풀린다.
