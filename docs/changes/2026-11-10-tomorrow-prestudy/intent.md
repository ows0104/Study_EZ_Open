# 캘린더 머리 「내일 예습」·새벽 4시 하루 기준

## Intent

사용자 2026-11-10 지시: 「페이지에서 "오늘 예습"을 "내일 예습"으로 수정하고, 하루가 넘어가는 기준을 새벽 4시로 바꿔줘.」

사용자 2026-11-11 추가 지시: 「노란 점 제거하고, 2, 3도 포함해서 작업해줘. 그리고 실습은 시험에 안 나오니까 빼줘.」

## Spec

- 캘린더 머리 줄(`today-board`)의 첫 칸 이름을 「내일 예습」으로 바꾼다.
  수는 **내일 날짜** 강의 중 예습 퀴즈가 있고 아직 끝내지 않은 강의 수다(전에는 오늘 날짜).
- 머리 줄의 「오늘」(내일 예습 기준일·D-day)은 한국시간 새벽 4시에 바뀐다. 4시 전은 전날로 센다.
  (11-10 당시 「하루 목표 학습일도 04시」라고 적었으나 틀렸다. Quiz Bank는 09시였다 — 아래 11-11 범위에서 04시로 맞춤.)
- 「내일 예습」 수에서 실습은 뺀다. 시간표에서 CBL·TBL도 category가 `practice`이므로
  `displayInfo`의 kind(`practice`)로 가른다. CBL·TBL·강의는 센다.
- 강의 칸의 노란 예습 점(`state-todo`: 점과 제목 굵기)을 없앤다.
- 「오늘 복습」 수는 서버 `reviewDue`를 그대로 쓴다(변경 없음).
- 이용 안내(`GuidePage`) 문장을 맞춘다. `redesign-prototype`은 시안이라 그대로 둔다.

## Plan

1. `web/src/calendar/CalendarPage.tsx`: `studyDayKey`(KST −4h 날짜), 내일 키로 필터(실습 제외), 이름 변경.
   `web/src/calendar/EventChip.tsx`·`web/src/styles/calendar.css`: `state-todo` 제거.
2. `web/src/notices/GuidePage.tsx` 안내 1줄, `web/src/styles/calendar.css` 주석.
3. 검사: `npm --prefix web run typecheck`, `npm --prefix web run build`, 03:59/04:00/23:30/00:30 경계 확인.

API·DB·출제 변경 없음.

## 검사 기록 (2026-11-11)

- `npm --prefix web run typecheck`, `npm --prefix web run build` 통과.
- 경계: 11-11 03:59 KST → 오늘 11-10·내일 11-11, 04:00 → 11-11·11-12, 23:30 → 11-11·11-12, 11-12 00:30 → 11-11·11-12.
- 고정물 `web/tests/redesign-shell.html`: 머리 「내일 예습」, 칸 점 없음. 11-12 강의 3·실습 1·CBL 1에 예습을 남긴
  임시 복사본에서 「내일 예습 4강의」(실습 제외, CBL 포함), 점 없음 확인. 임시 파일은 삭제.

## 범위 확장 (2026-11-11): 모든 날짜 전환을 새벽 4시로

사용자: 「일단 모든 날짜 전환의 기준은 새벽 4시로 설정해줘. 새벽 4시로 전환하는 과정에서 모순이 생기거나 막히는 게 있으면 알려줘.」

| 자리 | 전 | 후 |
|---|---|---|
| Quiz Bank 학습일 `server/app/study_engine/study_day.py` (오늘 목표·완료·다음날 복습·하루 계획·준비된 다음 문항 키) | 09시 | 04시 |
| 시험까지 남은 날 `study_engine/engine.py days_until` | 자정 | 04시 |
| 생성 큐의 하루 `server/app/jobs/queue.py` | 05시 | 04시 |
| Main-Quiz 새 목표 할당 남은 일수 `root_learning/planning.py` | 자정 | 04시(학습일은 이미 04시) |
| 웹 오늘 칸 강조 `CalendarGrid`·기본 블록 `studyBlocks`·D-day `labels.daysLabel`·기존 퀴즈 다음 복습 일수 `lecture/queue.daysFromNow` | 자정(브라우저 시간대) | 04시 KST (`entries.studyDayKey`) |
| 기존 퀴즈 복습 `srs.py`·Main-Quiz 학습일 | 04시 | 그대로 |

보류: Main-Quiz `root_learning/policy.py exam_limit`(시험까지 남은 날로 복습 간격 상한)은 자정 기준이다.
정책 `roots-adaptive/1` 안의 계산이고 저장된 평가를 재생할 때마다 다시 쓰여, 바꾸면 같은 정책 ID로 과거 일정이 달라진다.
새 정책 버전이 필요하므로 사용자 판단 전까지 두었다.

되돌림: 2026-10-19 사용자 요청(Quiz Bank 04→09시, `docs/deployment.md`)을 현재 지시로 되돌린다. 이유 기록은 없었다.

또 남는 것: 이전 Main-Quiz 정책(`day_hour: 9`)으로 이미 연 세션은 그 정책에 고정된 09시 경계를 계속 쓴다
(`server/tests/test_root_policy_api.py` 「legacy session still has its pinned 09:00 boundary」). 정책 고정 설계라 건드리지 않았다.

### 검사 기록 (2026-11-11, 범위 확장)

- 서버 `-m tests` 135개 중 133 통과. 실패 2(`test_root_map_tree`, `test_root_map_tree_v3`)는 로컬 venv에 PyMuPDF가 없어 import 단계에서 멈춘 것(이 변경과 무관).
  기존 09시·자정 가정이던 `test_study_day`·`test_study_engine`·`test_study_plan`·`test_root_policy_api`를 04시 기준으로 고쳤다.
- 웹 `typecheck`·`build`·`tests/study-blocks.test.cjs` 통과. `study-management.test.cjs`는 playwright 미설치로 실행 못 함.
