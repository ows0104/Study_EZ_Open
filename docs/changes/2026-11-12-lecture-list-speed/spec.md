# 강의 목록 정보 먼저 보이기 — 설계

## 요구사항과 수용 기준
- `useStudyTimetable`: `/api/timetable?include_study=false`만 읽는다. study-progress 묶음 읽기와 `onScope`를 없앤다.
- `useRootCatalog.ts`: `useRootSummaries(enabled)` 한 훅이 `{ rates, progress, loaded }`를 준다(한 요청, 60초 공유 캐시 유지).
  `prefetchRootCatalog()`로 강의 목록 페이지가 시간표와 동시에 요약 요청을 출발시킨다.
- `StudyOverview`: 행이 열렸는지·▶는 `marks.mainQuiz`(시간표)만 본다. Main-Quiz 행의 숫자 칸은 `loaded` 전 「…」(`is-loading`, aria-busy).
  위 통계(오늘 복습·학습률 평균·전체 카드)와 단계 범례도 같은 규칙.

## 책임·입출력 계약·오류 상태
- 서버 API는 그대로. `/api/timetable/study-progress`는 강의 패널(EventPanel)이 강의 하나로 계속 쓴다.
- 요약 실패: `fetchCatalog`가 빈 목록을 돌려 `loaded=true` → 숫자 칸 「—」, ▶는 켜진 채(열면 원래 오류가 보인다).
- 학습률은 서버가 계산한 `summary.score` 그대로(웹에서 다시 계산하지 않는다).

## 호환성과 데이터 보존
읽기 경로만 바뀐다. 학습 기록·문항·DB 쓰기 없음. 숨김(`/api/me/study-hidden`)·모아풀기·삭제 동작은 그대로.
