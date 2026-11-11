# Main-Quiz 학습률 통일과 Quiz Bank legacy화 — 설계

## 요구사항과 수용 기준

### R1. Main-Quiz 학습률 식 (한 곳에서 계산)
`server/app/root_learning/score.py`(새 파일)의 `lecture_score(doc, events, at, *, until=None)`가 유일한 정의다.
`until`은 셀 평가의 마지막 시각이고, 기본값은 `at`이다. 웹은 서버가 준 값을 그대로 쓰고 다시 계산하지 않는다.

**학습 상태 단위 u:** root-generation/4 문서는 문항(task), 그 전 문서는 방향(direction)이다. 지금 `replay`·`replay_tasks`와 같다.

1. **지금 숙련도:** 마지막 평가 이후 망각 곡선으로 깎은 값이다. 평가가 없으면 0이다.
   - 식은 `m_now = m / (1 + Δt / (9·S))`이다.
   - `Δt`는 일 단위 `at − lastAt`이다(최소 0).
   - `S`는 `max(0.25, ratingDays → baseDays → 1)`이다.
   - `next_mastery`가 평가 시점에 쓰는 것과 같은 망각 곡선이다.
2. **목표치 τ:** 평가가 저장한 `target`을 쓴다.
   - 없으면, 즉 2026-11-09 이전 평가나 아직 평가하지 않은 상태이면 `target_retention(문항, 개념 계획, target_parameters(), 내 중요도)`로 다시 계산한다.
   - 옛 문서처럼 방향 하나에 문항이 여럿이면 그중 가장 높은 목표치를 쓴다.
3. **문항(상태) 점수:** `s_u = min(m_now / τ, 1)`.
4. **방향 점수:** 그 방향 문항들의 `s_u` 평균이다(/4). 아직 상태가 없는 문항은 0이다. 옛 문서는 방향 상태의 `s_u`가 곧 방향 점수다.
5. **지도 목표 점수:** 필수(`required`) 방향 점수의 평균이다. 필수 방향이 하나도 없는 목표는 그 목표의 모든 방향 평균을 쓴다.
6. **강의 학습률:** 채택된 모든 지도 목표 점수 `t`로 `L = 1 − sqrt(mean((1 − t)²))`를 구한다.
   - 준비 전(문항 미준비) 목표도 0점으로 포함한다.
   - 표시값은 모든 목표가 1이면 100이고, 아니면 `min(99, round(100·L))`이다. 반올림으로 미달 강의가 100%로 보이지 않게 한다.
   - 지도 목표가 0개이면 `null`이다.
7. 반환값: `{score, status, targetCount, fullTargets, ratedTargets}`.
   - `status`는 `not_started`(평가 0), `needs_review`, `mastered` 중 하나다.

**수용 기준(새 서버 검사):**
- 평가가 없으면 0이다.
- 목표치에 도달한 평가 직후는 100이다.
- 같은 기록으로 시간이 지날수록 값이 단조 감소하고, 기한 직후에도 0이 아니다.
- 목표 [1, 0]은 29, [0.5, 0.5]는 50이다.
- 문항이 많이 붙은 지도 목표도 목표 하나의 비중이다.
- targetParameters 없는 옛 평가도 점수가 나온다.
- 옛 문서(방향 단위)와 /4 문서(문항 단위)가 둘 다 계산된다.

참고: `target_due`는 지금 숙련도가 목표치까지 떨어지는 시점을 복습일로 잡는다.
그래서 복습일까지는 그 문항 점수가 1로 유지되고, 복습일이 지나면 서서히 내려간다.
숙련도는 평가의 지수 평균이라 Good 한 번으로는 목표치에 닿지 않을 수 있다. 이는 Quiz Bank와 같은 성질이다.

### R2. 학습률이 나가는 모든 출구가 R1 하나를 쓴다
- **Main-Quiz 요약:** `root_learning/state.summary()`에 `score`(위 표시값)를 더한다.
  - 기존 `recalled`·`total` 같은 필드는 그대로 둔다.
  - 웹 `rootRate(summary)`는 `summary.score`를 반환한다.
- **강의 목록·캘린더·패널용 응답:** `lecture_mastery.lecture_overviews`가 내는 `mastery`를, 그 사용자에게 열린 Main-Quiz(`published_for`·`allowed`)의 R1 값으로 바꾼다.
  - 대상 응답: `GET /api/timetable`, `POST /api/timetable/study-progress`, `GET /api/lectures/{s}/{r}`.
  - 모양은 기존 `LectureMastery`와 호환되게 낸다. `scope:"main-quiz"`, `conceptCount`=지도 목표 수, `masteredConcepts`=만점 목표 수, `weakest:[]`.
  - Main-Quiz가 없는 강의는 `mastery: null`이다. Quiz Bank 값으로 돌아가는 길은 없다.
- **카드 단계·오늘 복습(`cardProgress`):** 「강의 목록 숫자 열」 작업이 만든 Main-Quiz 문항 단계 집계를 쓴다. 그 작업이 병합된 뒤 그 함수에 연결한다.
- **웹:** 강의 목록 행·「학습률 평균」(StudyOverview), 캘린더 막대(ChipLearning·EventChip), 사이드 패널(EventPanel), 강의 페이지 배지(LectureMastery)는 위 값 하나만 읽는다.
  - 평균은 지금처럼 평가 가능한 강의의 평균이다.
  - 「Quiz Bank가 있으면 Quiz Bank 우선」 분기를 없앤다.

### R3. 시험별 하루 목표 계획 (Quiz Bank에서 가져옴)
- `GET /api/study-plan`의 시험 묶기, 망각 보정 하루 확보량(`balanced_daily_gain`), 응답 필드는 유지한다.
- 강의 점수만 R1으로 바꾼다.
  - 오늘 시작 B는 「04시 이전 평가, 04시 평가」로 구한다.
  - 오늘 끝 예상 F는 「04시 이전 평가, horizon 평가」, 현재값은 「지금까지 평가, 지금 평가」로 구한다.
  - 이렇게 R1에 `until`(셀 평가의 마지막 시각)과 `at`(평가 시각)을 따로 준다.
- 문제가 없는 강의(이 사용자에게 열린 Main-Quiz가 없는 강의)는 0으로 포함하고 `unassessedLectures`로 센다.
- 도달 시각은 시험 시작 **48시간 전**이다. `bufferDays: 2`이며, Main-Quiz 정책 `deadline_offset: 2`와 같다.
- 강의별 오늘 복습 목표(`lectureGoal`, Quiz Bank daily queue)는 `null`로 둔다. Main-Quiz의 오늘 할 일은 기존 `RootToday`가 보인다.
- 「오늘 푼 문항 수」류 필드는 Main-Quiz 평가 이벤트로 센다.

### R4. Quiz Bank legacy화 (학생 화면)
- 학생 화면에서 Quiz Bank 학습률, 「모아풀기」, Quiz Bank 카탈로그 링크, Quiz Bank 학습 시작 카드를 없앤다.
  - 대상 위치: StudyOverview·BankPanel·BankStart·EventPanel의 Quiz Bank 분기.
  - 강의 링크는 Main-Quiz로만 간다.
- 옛 기록은 `?legacy=1`(기존 「기존 문제·기록 보기」)로만 연다. legacy 화면에는 「옛 Quiz Bank 기록(학습률에 포함되지 않음)」이라고 적는다.
- 관리자 Quiz Bank 도구(신고·문항 검토·공개)와 서버 `/bank/*` 엔드포인트는 그대로 둔다. legacy 화면과 기록 보존에 필요하다.
- 안내(GuidePage)·`server/README.md`·`docs/map.md`·관련 CLAUDE.md의 학습률 설명을 R1·R3로 고친다.

## 책임·입출력 계약·오류 상태
- 계산 책임은 `server/app/root_learning/score.py`에 둔다. 다른 모듈은 이 함수만 부르고, 웹은 표시만 한다.
- 이벤트 재생은 기존 `replay`/`replay_tasks`를 그대로 쓴다. `undo`·equivalence·문항 지문 규칙은 바뀌지 않는다.
- Main-Quiz 정책이 꺼져 있으면(`configured_policy()`가 None) `summary`가 None이다. 그때 `mastery`도 null이고, 화면은 「—」로 보인다.
- 점수 계산 중 예외가 나면 그 강의만 `mastery: null`로 둔다. 응답 전체를 500으로 만들지 않고 로그를 남긴다.
- API 경로는 새로 생기거나 사라지지 않는다. `test_route_contract` 목록은 그대로다.
- `summary.score`와 `mastery.scope:"main-quiz"`가 필드로 추가될 뿐이다.

## 호환성과 데이터 보존
- DB 스키마·migration이 없다. 학습 이벤트·BankState·QuizBank 행을 읽기만 하고 쓰지 않는다.
- 학습 기록·개인 수정·제외 문항·검수 이력은 그대로다. Quiz Bank 기록은 legacy 화면에서 그대로 보인다.
- 평가 이벤트의 저장 형식과 복습일 계산(`target_due`·`effective_due`)은 바뀌지 않는다. 학습률은 읽기 전용 파생값이다.
- Quiz Bank 코드는 이번에 옮기거나 지우지 않는다. `study_engine`은 legacy 화면과 관리자 도구가 계속 쓴다.
