# 강의록 회독 기록과 강의별 짧은 메모 — 구현 계획

## 변경 범위·대상 파일·순서
1. 서버: `server/app/models/lecture_notes.py`(NoteRead·LectureMemo+RLS), `models/__init__.py`, `routes/lecture_notes.py`(3 경로·집계 도우미),
   `main.py` 등록, `routes/lectures.py`(상세 `noteReads`·`myMemo`), `routes/timetable.py`(`noteReads`),
   `routes/usage.py`·`usage_actions.py`(이용현황 두 행동).
2. 서버 검사: `server/tests/test_lecture_notes.py`(새), `tests/test_route_contract.py` 3줄.
3. 웹: `web/src/calendar/ReadEditor.tsx`(회독 편집·메모, 새), `EventPanel.tsx` 통계 두 줄, `ChipLearning.tsx` 강의록 토막,
   `useCalendarTimetable.ts`(패널 변경을 칸에 반영), `web/src/types/lectures.ts`, `web/src/styles/calendar.css`,
   `web/src/notices/GuidePage.tsx` 문장, 고정물 `web/tests/lecture-reads-memo.(html|tsx)`.

## 검사 명령과 성공 조건
- server(격리 sqlite): `-m tests lecture_notes`, `-m tests route_contract`, `-m tests usage`, 전체 `-m tests`.
- web: `npm run typecheck`, `npm run build`.
- 고정물 `tests/lecture-reads-memo.html?predone&reads=2`: +·지우기·되돌리기 요청과 토막 수, 메모 PUT 확인.

## 위험·복원·승인할 범위
- 요청 발언이 로컬 구현·검사·커밋·PR 승인이다.
- 별도 승인: 운영 DB에 표 두 개 생성(`python -m app.cli init-db` = create_all, 기존 표 미변경) → 그 뒤 master 병합(자동 배포).
- 표 없이 API가 먼저 나가면 강의 상세·시간표가 500이 된다(새 표를 읽음) → 반드시 DB 먼저.
- 복원: PR revert. 표는 남겨도 무해하며 지우는 것은 따로 승인.
