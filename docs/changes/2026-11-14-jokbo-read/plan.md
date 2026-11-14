# 족보 1회 풀이를 회독에 기록 — 구현 계획

## 변경 범위·대상 파일·순서
1. 서버: `server/app/models/jokbo.py`(JokboRound, RLS), `models/__init__.py`, `routes/jokbo.py`(rounds POST·칸별 수),
   `routes/timetable.py`(`jokboRounds`), `tests/test_jokbo.py`, `tests/test_route_contract.py`(새 경로).
2. 웹: `web/src/jokbo/JokboPage.tsx`, `web/src/types/lectures.ts`, `web/src/calendar/entries.ts`·`ChipLearning.tsx`·
   `EventChip.tsx`·`EventPanel.tsx`·`ReadEditor.tsx`, `web/src/styles/calendar.css`, `web/src/notices/GuidePage.tsx`.
3. 운영 표: `create_table.py`(이 표 하나만 create_all, RLS 확인). 러너 PC에서 사람이 병합 전에 실행.
4. `docs/deployment.md`에 배포 전 표 생성 한 줄.

## 검사 명령과 성공 조건
- 서버(`server/`): `.venv/Scripts/python.exe -m tests jokbo`, `route_contract`, 시간표를 읽는 검사
  (`lecture_notes`·`root_timetable_mark`·`bank_timeline`·`lecture_mastery`·`quiz_publication`·`root_optional_exclusion`·
  `root_rate_api`·`smoke`·`study_loading`·`study_management`) 통과. 모두 임시 SQLite·임시 저장소.
- 웹: `npm --prefix web run typecheck`, `npm --prefix web run build` 통과.
- PR CI `Tests and build` 통과.

## 위험·복원·승인할 범위
- 위험: 표 없이 API가 먼저 배포되면 `/api/timetable` 학습 집계가 실패한다 → 표 생성 후 병합.
- 복원: PR revert. 표는 남겨 둬도 옛 코드에 영향 없음.
- 승인 범위: 위 파일의 로컬 구현·검사·Draft PR까지. 운영 표 생성(러너 PC)과 master 병합(=자동 배포)은 사람이 한다.
