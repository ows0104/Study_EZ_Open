# Main-Quiz 학습률 통일과 Quiz Bank legacy화 — 배포 준비

## 코드 리뷰·검증 결과
- 서버 검사(`server/.venv` + `PYTHONPATH=..`, 격리된 로컬 SQLite):
  - 137개 중 135개가 통과했다.
  - 실패 2개(`test_root_map_tree`, `test_root_map_tree_v3`)는 이 PC에 PyMuPDF가 없어서 난다. 변경 전과 같다.
  - 새 검사: `test_root_score`(R1 수용 기준), `test_root_rate_api`(시간표·상세·study-progress·요약이 같은 숫자).
  - 다시 쓴 검사: `test_study_plan`(48시간·Main-Quiz 이벤트).
  - 고친 검사: `test_lecture_mastery`, `test_study_loading`, `test_study_day`, `test_bank_personal_questions`(legacy 경로).
- `pytest tests/contracts`: 376개 모두 통과했다.
- 웹:
  - `typecheck`·`build`가 통과했다.
  - `node --test web/tests/*.test.cjs`는 24개가 통과했다.
  - 18개는 실패하지만, 깨끗한 origin/master(4cffe9a6)에서도 같은 18개가 실패한다. 새 실패는 0이다. CI는 이 검사들을 돌리지 않는다.
- 브라우저: `web/tests/study-overview.html` 고정물로 확인했다.
  - 행 학습률이 `summary.score`이다.
  - 학습률 평균은 Main-Quiz 강의만의 평균이다(82·61·34·12·18 → 41%).
  - Quiz Bank만 있는 강의는 「—」이고 복습 단추가 꺼져 있다. 모아풀기 선택도 없다.
  - 콘솔 오류는 0이다.
- 생각해 둘 점: 숙련도가 지수 평균(α 0.35)이라 Good 한 번이면 문항 점수가 목표치의 약 40%다. 한 목표를 만점으로 채우려면 서로 다른 날 Good을 약 3번 받아야 한다(Quiz Bank와 같은 성질).

## 배포 대상 버전·순서·데이터 변경
- 브랜치 `claude/main-quiz-learning-rate`. master에 병합하면 API(Cloud Run)와 웹(Pages)이 자동 배포된다.
- DB 스키마·migration·운영 데이터 쓰기가 없다. 학습 이벤트·BankState·QuizBank 행은 읽기만 한다.
- 응답 변화:
  - `mastery` 모양이 Main-Quiz용으로 바뀐다(`scope:"main-quiz"`, `targetCount`·`fullTargets`·`ratedTargets`).
  - `cardProgress`는 null이다(문항 단계는 `/api/root-learning`의 `questionProgress`).
  - `summary.score`가 추가된다.
  - `/api/study-plan`이 Main-Quiz 기준이 된다. `bufferDays` 2, `lectureGoal` null.
- PR #99(캘린더 머리 「오늘 복습」을 study-plan 기준으로)와 `GuidePage.tsx`가 겹친다. 나중에 병합하는 쪽이 문구를 맞춘다.
  - 캘린더 머리의 옛 `useTodayDue`(Quiz Bank `cardProgress.reviewDue` 합)는 이 변경 뒤 0이 된다.
  - PR #99가 그 칸을 study-plan으로 바꾸므로, #99를 먼저 또는 함께 병합하는 것이 좋다.

## 배포 후 확인·롤백·필요한 사람 승인
- 확인 1: 운영 `/api/timetable`의 Main-Quiz 강의 `mastery.scope == "main-quiz"`인지 본다.
- 확인 2: 강의 목록·캘린더 칩·패널·시험 계획에서 한 강의의 숫자가 같은지 본다.
- 확인 3: `?legacy=1`이 열리는지 본다.
- 롤백: 병합 커밋을 revert하면 이전 Cloud Run revision·Pages로 돌아간다. 데이터 변경이 없다.
- 병합(=배포)은 사용자가 정한다. 학생이 보는 숫자가 바뀌는 배포다.
