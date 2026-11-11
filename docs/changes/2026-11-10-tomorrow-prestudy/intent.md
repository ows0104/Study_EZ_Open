# 캘린더 머리 「내일 예습」·새벽 4시 하루 기준

## Intent

사용자 2026-11-10 지시: 「페이지에서 "오늘 예습"을 "내일 예습"으로 수정하고, 하루가 넘어가는 기준을 새벽 4시로 바꿔줘.」

사용자 2026-11-11 추가 지시: 「노란 점 제거하고, 2, 3도 포함해서 작업해줘. 그리고 실습은 시험에 안 나오니까 빼줘.」

## Spec

- 캘린더 머리 줄(`today-board`)의 첫 칸 이름을 「내일 예습」으로 바꾼다.
  수는 **내일 날짜** 강의 중 예습 퀴즈가 있고 아직 끝내지 않은 강의 수다(전에는 오늘 날짜).
- 머리 줄의 「오늘」(내일 예습 기준일·D-day)은 한국시간 새벽 4시에 바뀐다. 4시 전은 전날로 센다.
  Main-Quiz·하루 목표의 학습일(한국시간 04:00)과 같은 기준이다.
- 「내일 예습」 수에서 실습은 뺀다. 시간표에서 CBL·TBL도 category가 `practice`이므로
  `displayInfo`의 kind(`practice`)로 가른다. CBL·TBL·강의는 센다.
- 강의 칸의 노란 예습 점(`state-todo`: 점과 제목 굵기)을 없앤다.
- 「오늘 복습」 수는 서버 `reviewDue`를 그대로 쓴다(변경 없음).
- 격자의 오늘 칸 강조(`CalendarGrid`)는 달력 날짜이므로 자정 기준을 유지한다.
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
