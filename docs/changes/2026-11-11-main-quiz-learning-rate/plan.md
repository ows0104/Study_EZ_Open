# Main-Quiz 학습률 통일과 Quiz Bank legacy화 — 구현 계획

## 시작 조건
- 아래 두 작업이 master에 병합된 뒤, 이 브랜치를 최신 `origin/master`로 rebase하고 나서 시작한다.
  - 「강의 목록 Main-Quiz 숫자 열」(`claude/main-quiz-list-columns`)
  - 「내일 예습·새벽 4시」(PR #97)
- 둘 다 `StudyOverview`·`useRootCatalog`·`EventPanel`·`root_learning/state.py`·`root_learning/policy.py`·`routes/study_plan.py`·`study_engine`을 고친다.
- 그 전에는 이 작업 폴더 문서만 바꾼다.
- 병합 시점에 대시보드를 다시 확인한다(3번 단계). 새로 겹친 행이 있으면 조정한다.

## 변경 범위·대상 파일·순서

**1. 계산 (서버)**
- `server/app/root_learning/score.py`(새 파일): `lecture_score`(spec R1).
- `server/app/root_learning/state.py`: `summary()`에 `score`를 더한다.
- `server/tests/test_root_score.py`(새 파일): spec R1의 수용 기준을 하나씩 검사한다.

**2. 출구 (서버)**
- `server/app/lecture_mastery.py`: `lecture_overviews`의 `mastery`를 Main-Quiz R1 값으로 바꾼다.
  - 사용자에게 열린 Main-Quiz 문서와 이벤트는 한 번에 읽는다(강의 수만큼 반복 조회하지 않는다).
  - `cardProgress`는 숫자 열 작업의 Main-Quiz 문항 단계 집계로 바꾼다.
- `server/app/routes/timetable.py`, `routes/lectures.py`: `marks.quiz`를 학습률 판단에 쓰지 않게 정리한다. `/bank` 응답은 legacy 그대로 둔다.
- `server/app/study_engine/planning.py`:
  - `daily_plan`이 강의 점수 함수를 인자로 받게 일반화한다.
  - 도달 시각은 시험 시작 48시간 전, `bufferDays`는 2로 한다.
  - Quiz Bank 전용 코드는 legacy 화면만 쓰도록 남긴다.
- `server/app/routes/study_plan.py`: unit을 Main-Quiz 문서·이벤트로 만든다. `lectureGoal`은 null이다.
- 고칠 검사:
  - `server/tests/test_study_plan.py`, `test_lecture_mastery.py`, `test_study_loading.py`, `test_study_day.py`(48시간)
  - Main-Quiz 쪽 `test_root_*`: summary 필드 추가만 확인한다.

**3. 웹**
- `web/src/bank/useRootCatalog.ts`: `rootRate` → `summary.score`.
- `web/src/types/rootLearning.ts`, `types/mastery.ts`: `score`, `scope:"main-quiz"`.
- `web/src/bank/StudyOverview.tsx`: 행 학습률·「학습률 평균」·단계 합계를 Main-Quiz만으로 한다. 모아풀기·Quiz Bank 카탈로그 링크를 없앤다.
- `web/src/calendar/ChipLearning.tsx`, `EventChip.tsx`, `EventPanel.tsx`: Quiz Bank 우선 분기를 없애고 Main-Quiz 하나만 쓴다.
- `web/src/calendar/useTodayDue.ts`: 오늘 복습 수를 Main-Quiz 문항 단계 집계에서 받는다.
- `web/src/calendar/StudyPlanBoard.tsx`: 「2일 전」, Main-Quiz 기준 문구.
- `web/src/lecture/LectureMastery.tsx`(LecturePage 배지): 「Main-Quiz 기준」.
- `web/src/bank/BankPanel.tsx`, `BankStart.tsx`, `BankStudy.tsx`: Quiz Bank 시작 카드·카탈로그 링크를 학생에게 숨긴다. `?legacy=1` 화면에 「옛 Quiz Bank 기록 — 학습률에 포함되지 않음」을 붙인다.
- 고칠 검사: `web/tests/study-blocks.test.cjs`, `calendar-loading.test.cjs`, `study-management.test.cjs`, `study-loading.test.cjs`와 각 fixture.

**4. 문서**
- `web/src/notices/GuidePage.tsx`: 학습률·2일 전·Quiz Bank 문구.
- `server/README.md`: 「Quiz Bank 학습도」는 legacy로 표시하고 Main-Quiz 학습률 절을 새로 쓴다. 「시험별 하루 목표」는 48시간으로 고친다.
- `docs/map.md`, `docs/architecture.md`, `web/CLAUDE.md`, `server/CLAUDE.md`, `server/app/routes/bank_api/CLAUDE.md`: Quiz Bank는 legacy이고 학습률은 Main-Quiz라고 적는다.

## 검사 명령과 성공 조건
- `server/.venv/Scripts/python -m pytest server/tests -q`(`PYTHONPATH=..`, 격리된 로컬 SQLite): 새 검사와 고친 검사가 통과한다.
  - 기존 실패가 있으면 master에서 같은 실패를 재현해 구분한다.
- `python -m pytest tests/contracts -q`: 통과한다.
- `npm --prefix web run typecheck`, `npm --prefix web run build`, `node --test web/tests/*.test.cjs`: 통과한다.
- 로컬 서버와 고정물로 브라우저 확인:
  - 강의 목록·캘린더·패널·계획판의 학습률이 같은 강의에서 같은 숫자다.
  - Quiz Bank 단추가 학생 화면에 없다.
  - `?legacy=1`은 열린다.
- 운영 DB는 읽지도 쓰지 않는다. `server/.env` 대신 `DATABASE_URL`을 로컬 파일로 지정한다.

## 위험·복원·승인할 범위
- **성능:** 타임테이블 응답이 강의마다 Main-Quiz 이벤트를 재생한다. 이미 `/api/root-learning` 목록이 같은 일을 한다. 로컬에서 강의 수만큼의 응답 시간을 재서 release.md에 적는다.
- **숫자 변화:** 배포 순간 학생이 보던 학습률이 바뀐다.
  - Quiz Bank 값에서 Main-Quiz 값으로 바뀐다.
  - Main-Quiz 값도 「회상 가능 비율」에서 「부분 점수 RMS」로 바뀐다.
  - 안내 문구를 함께 바꾼다.
- **과거 블럭:** Quiz Bank만 있는 지난 강의는 학습률이 「—」로 보인다. 옛 기록은 legacy 화면에 남는다.
- **복원:** 커밋 revert로 되돌린다. 병합하면 API는 Cloud Run, 웹은 Pages에 자동 배포된다. DB 변경이 없어 되돌리기만으로 원상태다.
- **승인할 범위:** 위 파일 목록과 이 작업 폴더. DB·생성기·러너·프롬프트·평가 저장 형식은 바꾸지 않는다.
- **이번에 하지 않는 것:** Quiz Bank 코드를 `legacy/` 폴더로 옮기거나 지우는 일, 서버 `/bank/*` 엔드포인트 삭제. 원하면 별도 작업으로 한다.
