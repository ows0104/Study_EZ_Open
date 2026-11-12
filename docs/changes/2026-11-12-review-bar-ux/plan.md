# 복습바·로딩 속도·풀이 바·Ctrl+Z — 구현 계획

## 변경 범위·대상 파일·순서

1. `server/app/root_learning/state.py`: `replay_tasks`의 지문을 필요할 때만, 가벼운 문서의 미리 계산한 지문 우선.
2. `server/app/root_learning/light.py`(새): `LightDocument`, `light_rows(db, keys)` 캐시.
3. `server/app/lecture_mastery.py`: `main_quiz_inputs`가 가벼운 문서를 쓴다.
4. `server/app/routes/root_learning.py`: `catalog()`가 가벼운 문서를 쓰고 강의별 실패를 건너뛴다.
5. `server/tests/test_root_light.py`(새): 지문 지연 계산이 이전 판 이력을 그대로 잇는지, 가벼운 문서 결과 동일·캐시 재사용, 목록 부분 실패.
6. `web/src/calendar/useCalendarTimetable.ts`(동시 요청), `web/src/bank/useStudyTimetable.ts`(동시 3·포커스 60초).
7. `web/src/calendar/ChipLearning.tsx`, `EventChip.tsx`, `CalendarPage.tsx`(범례), `web/src/styles/calendar.css`: 복습 막대.
8. `web/src/bank/RootSolve.tsx`, `web/src/bank/main-quiz.css`: 스페이스·Ctrl+Z·아래 바.
9. `web/src/notices/GuidePage.tsx`: Ctrl+Z 안내.

## 검사 명령과 성공 조건

- server: `server/`에서 `PYTHONPATH=..` + `.venv/Scripts/python.exe -m tests root`(격리 SQLite). 새 테스트 포함 통과.
- 실제 데이터 동일성: 읽기 전용으로 받은 23편 문서·상위 두 계정 이벤트로 원본/가벼운 문서 결과 비교 스크립트(로그는 시간·개수만).
- web: `npm --prefix web run typecheck`, 기존 `web/tests` 키 고정물(root-choice-keys 등) ALL PASSED, Ctrl+Z·스페이스 사례 추가.
- 브라우저: web-fixtures로 캘린더 칸·풀이 바 확인.

## 위험·복원·승인할 범위

- 위험: 가벼운 문서에 빠진 `stimuli`를 읽는 계산이 새로 생기면 결과가 달라진다 → 동일성 검사와 테스트가 막는다.
  메모리: 가벼운 문서 23편 수십 MB. 상한 32편.
- 복원: 커밋 되돌리기. 데이터 변경 없음.
- 승인 범위: 위 파일·검사·문서, PR. 사용자 요청이 구현 승인이고 되돌릴 수 있는 코드 배포다(개발 루프 「사람에게 묻는 것」에 닿지 않음).
