# Main-Quiz 오늘 학습 중요도 필터 — 구현 계획

## 변경 범위·대상 파일·순서

1. `server/app/root_learning/content.py`: `task_tiers(doc, tiers)`(과제→실효 중요도), `focus_for(db, subject, user_id)`(마지막 선택, 없으면 TIERS).
2. `server/app/routes/root_learning.py`: `overview_data`만 — 거른 `available`로 plan, 응답에 `focus`, 재개 대상은 같은 focus 회차만.
   `start`에서 새 회차 `state.focus`(모두 선택이 아닐 때만). 새 `RootFocus` 모델·`PUT BASE + '/focus'`(「내 중요도」와 같은 PUT).
   앞면·답면·prior_exposure(선지 보기 #118 영역)는 건드리지 않는다.
3. `web/src/types/rootLearning.ts`: `RootFocus`, `RootOverview.focus?`.
4. `web/src/bank/RootToday.tsx`: 오늘 추천 카드 안 칩 4개(`onFocus` prop). `RootLearning.tsx`: 저장 호출 후 overview 갱신.
5. `web/src/bank/main-quiz.css`: `.mq-focus` 칩 스타일만(카드 영역, 풀이 화면 스타일 무관). 모바일 폭 확인.
6. 검사: 새 `server/tests/test_root_focus.py` — 계획 거름, summary 분모 불변, 모두 선택 시 세션 ID·계획 불변, 재개 조건,
   빈/잘못된 tiers 422, 멱등, 「내 중요도」 반영. 기존 `test_root_api`·`test_root_planning`·`test_root_learning_v4` 회귀.
7. PR → master 병합(=API·웹 자동 배포). 병합 뒤 대시보드 행 정리.

## 검사 명령과 성공 조건

- server: `server/`에서 `PYTHONPATH=.. .venv/Scripts/python.exe -m tests root` (격리된 로컬 테스트 DB, server/.env 운영 DB 미사용).
- web: `web/`에서 `npm run build`(타입 검사 포함).
- 브라우저: 로컬 fixture 서버(`server/tests/serve_root_fixture.py`)로 칩 토글·숫자 갱신·시작·모바일 폭 확인, 스크린샷.
- 실패·미실행·기존 결함은 release.md에 구분해 적는다.

## 위험·복원·승인할 범위

- 위험: 선택을 잊고 Optional이 계속 빠진 채 시험 직전까지 갈 수 있다 → 칩이 시작 버튼 옆에 늘 보인다.
- 위험: 진행 중 회차에서 칩을 바꾸면 그 회차는 재개되지 않는다(R5). 기록은 남는다.
- 복원: 코드 `git revert`. 남는 focus 이벤트는 다른 집계가 무시하므로 지울 필요 없다.
- 승인할 범위: 위 파일의 로컬 구현·검사, PR, master 병합(자동 배포). DB 스키마·운영 데이터·문항 변경 없음.
