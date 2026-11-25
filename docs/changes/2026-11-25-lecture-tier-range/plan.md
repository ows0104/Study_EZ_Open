# Main-Quiz 중요도 필터 강의별 저장·범위 슬라이더 — 구현 계획

## 변경 범위·대상 파일·순서

1. `server/app/root_learning/content.py`: `focus_for`·`focus_prereqs`·`_last_focus`·`focus_events`에 run_id 조건.
2. `server/app/routes/root_learning.py`: 호출부 세 곳(강의 목록 overview, `overview_data`, `save_focus`)에 run_id 전달. 다른 구역은 안 건드린다.
3. `web/src/bank/RootToday.tsx`: `FocusChips` → `FocusRange`(손잡이 둘인 범위 + 선행 문항 버튼). `onFocus` prop·`RootLearning.tsx`는 그대로.
4. `web/src/bank/main-quiz.css`: `.mq-focus` 구역만 슬라이더 모양으로. 모바일 폭(375px) 확인.
5. 검사: `server/tests/test_root_focus.py`에 같은 과목 두 강의 분리·처음 값·seq 분리 검사 추가. 기존 `test_root_prereq_toggle` 회귀.
6. PR(Draft) → 사용자 확인 뒤 master 병합(=API·웹 자동 배포). 병합 뒤 대시보드 행 정리.

## 검사 명령과 성공 조건

- server: `server/`에서 `PYTHONPATH=.. .venv/Scripts/python.exe -m tests root` (격리된 로컬 테스트 DB, server/.env 운영 DB 미사용).
- web: `web/`에서 `npm run build`(타입 검사 포함).
- 브라우저: 로컬 fixture 서버로 끌기·키보드·저장 한 번·숫자 갱신·모바일 폭, 스크린샷.
- 실패·미실행·기존 결함은 release.md에 구분해 적는다.

## 위험·복원·승인할 범위

- 위험: 직접 바꾼 적 없는 강의는 처음 값이 Essential~Important라 Optional이 오늘 계획에서 빠진다(L2). 슬라이더가 늘 보인다.
- 위험: 비연속 옛 선택은 슬라이더 모양과 실제 거름이 처음 움직일 때까지 다르다(L4).
- 복원: 코드 `git revert`. focus 이벤트는 그대로라 되돌리면 과목 단위 읽기로 돌아간다.
- 승인할 범위: 위 파일의 로컬 구현·검사, Draft PR. master 병합(배포)은 따로 확인. DB 스키마·운영 데이터·문항 변경 없음.
