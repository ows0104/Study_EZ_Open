# Main-Quiz 오늘 학습 이어 풀기 — 구현 계획

## 변경 범위·대상 파일·순서

1. `server/app/root_learning/planning.py`: `plan`·`plan_tasks`(옛 판의 `plan`도)에 `new_goals` 인자. 기본값은 지금과 같다.
2. `server/app/routes/root_learning.py`:
   - `today_stream(db, row, user, when, configured)` — 오늘 흐름 하나(R1).
   - `overview_data`: 재개 대상 = 끝나지 않은 오늘 흐름, `todayDone` 추가.
   - `start`: 흐름이 끝났으면 뒤에 붙이기(R3), 없으면 지금처럼 새로.
   - `save_focus`: 흐름의 뒷부분 교체(R2, 학습일 시작 상태로 다시 계획), 버전 잠금.
3. `web/src/types/rootLearning.ts`: `RootOverview.todayDone?`.
4. `web/src/bank/RootToday.tsx`: 버튼 이름 셋(R4). `RootLearning.tsx`: 칩 저장 뒤 미리 받은 문항 비우기(`forget`)·남은 수 다시 읽기.
   RootSolve.tsx(#162 진행 중)는 건드리지 않는다.
5. `web/src/notices/GuidePage.tsx`: 중요도 칩 안내가 있으면 한 줄 고침.
6. 검사: `server/tests/test_root_focus.py`에 — 칩 바꿔도 같은 세션·앞부분·번호 유지, 답 연 과제 유지, 새 목표 수 불변,
   껐다 켜면 원래 남은 목록과 같음, 끝난 흐름에 더 풀기로 이어 붙음(번호 이어짐), 붙일 것 없으면 409, 버전 경합 409,
   칩 모두 선택·흐름 없음은 지금과 같음. 기존 root·main_quiz 묶음 회귀.

## 검사 명령과 성공 조건

- server: `server/`에서 `PYTHONPATH=.. PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m tests root main_quiz`
  (격리된 로컬 테스트 DB. server/.env 운영 DB 미사용).
- web: `web/`에서 `npm run build`(타입 검사 포함).
- 브라우저: 로컬 fixture 서버(`server/tests/serve_root_fixture.py`)로 몇 문항 푼 뒤 칩 끄기·켜기 → 재개 번호 확인,
  끝까지 푼 뒤 「더 풀기」 → 번호 이어짐, 스크린샷.
- 실패·미실행·기존 결함은 release.md에 구분해 적는다.

## 위험·복원·승인할 범위

- 위험: 칩을 바꾼 순간 다른 탭에서 풀던 화면은 다음 저장이 409가 된다 → 기존 「서버 기록 불러오기」로 회복.
- 위험: 새 목표 몫 계산을 「흐름에 있던 미학습 목표 수」로 고정하므로, 칩을 줄여 그 목표의 과제가 다 빠지면 다음 목표로 채워진다(개수는 같다).
- 복원: 코드 `git revert`. 남는 데이터는 길어진 세션 tasks뿐이고 옛 코드가 그대로 읽는다.
- 승인할 범위: 위 파일의 로컬 구현·검사, Draft PR. master 병합(=API·웹 자동 배포)은 따로 승인. DB 스키마·운영 데이터·문항 변경 없음.
