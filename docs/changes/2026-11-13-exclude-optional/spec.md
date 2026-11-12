# Optional 문항 계산 제외 토글 — 설계

## 요구사항과 수용 기준
- 강의 목록(StudyOverview) 「유형별/순서대로」 줄 맨 오른쪽에 토글 버튼 `Optional 제외`(aria-pressed). 설명 문구는 달지 않는다.
- 값은 **계정 단위**로 서버에 저장한다. 같은 계정이면 어느 기기·화면에서도 같은 값이 적용된다. 기본값은 꺼짐.
- 켜짐일 때 Optional 문항은 아래 계산에서 없는 것처럼 빠진다. 꺼짐이면 지금과 같은 값이 나온다(회귀 없음).
  - 학습률 `lecture_score`: 강의 목록·캘린더 막대·강의 패널·강의 페이지·Main-Quiz 시작 화면·풀이 중 머리줄·시험 계획 진척.
  - 카드 수 `question_progress`: 전체·미열람·인식·회상·유지·오늘 복습.
  - 목표 요약 `summary`: total·learned·recalled·unseen·unready·importantUnseen·newToday.
  - 시험 계획의 오늘 복습 수(`reviewsToday`).
- 바뀌지 않는 것: 문항 목록·풀이·답 보기·평가 기록·복습 일정·오늘 계획(Optional 칩은 별도 기존 필터)·개념 지도 표시·Optional 칩 개수·내 중요도 변경 기능.
- 토글을 누르면 현재 화면의 수치가 다시 불러와지고, 다른 화면으로 이동해도 캐시된 옛 값이 보이지 않는다.

## 책임·입출력 계약·오류 상태
- Optional 판정: `content.task_tiers`(내 중요도 → 판의 tier → 'Core') 결과가 `Optional`인 task. 내가 Optional로 바꾼 문항도 빠지고, Optional에서 올린 문항은 포함된다.
- 목표·방향에는 tier가 없으므로 문항에서 유도한다.
  - /4 문서: 방향 점수는 남은(비Optional) 문항만 평균. 남은 문항이 없는 방향은 제외.
  - 이전 문서: 방향 상태를 문항별로 나눌 수 없어, 방향의 모든 문항이 Optional일 때만 방향을 제외.
  - 남은 방향이 없는 목표는 total을 포함한 모든 집계에서 제외. 목표가 하나도 남지 않으면 학습률은 기존 「값 없음」과 같은 `None`.
- 저장: 새 표 없이 append-only `root_event`에 `kind='optional'`, subject·run_id·revision·session_id는 빈 문자열, payload `{_request, exclude: bool, seq}`. 최신 (seq, created_at)이 현재 값.
- API: `GET /api/root-learning/optional` → `{exclude}`, `PUT` 같은 경로 `{exclude, requestId}` → `{exclude}`. 승인된 사용자만. 같은 requestId 재전송은 한 번만 기록.
- 서버의 `overview_data`·`lecture_overviews`·`lecture_masteries`·study_plan이 요청 사용자의 값을 읽어 계산한다(쿼리 파라미터 없음).
- 오류: PUT 실패 시 버튼은 이전 값으로 돌아가고 수치는 바뀌지 않는다.

## 호환성과 데이터 보존
- DB 스키마·migration 없음. 기존 문항·ID·기록·내 중요도·제외 문항은 읽기만 한다.
- `content.availability`와 `planning.plan`에 넘기는 `available`은 거르지 않는다(2026-11-12 선행 문항 500 재발 방지). 계산용 집합만 거른다.
- 빈 subject의 `root_event`는 `events_for`(subject·run_id 필터)와 사용 현황 집계(reveal/rate만)에 들어가지 않는다.
- 옛 웹은 새 필드를 몰라도 동작한다(값을 끈 상태와 같음).
