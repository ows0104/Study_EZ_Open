# Optional 문항 계산 제외 토글 — 구현 계획

## 변경 범위·대상 파일·순서
1. 서버 저장: `server/app/root_learning/content.py`에 `optional_excluded(db, user_id)`·`optional_ids(doc, tiers)`;
   `server/app/routes/root_learning.py`에 `GET/PUT /root-learning/optional`.
2. 서버 계산:
   - `server/app/root_learning/score.py` `lecture_score(..., exclude=None)` — 형제 문항·방향·목표에서 제외 집합 반영.
   - `server/app/root_learning/state.py` `summary`·`question_progress`·`replay` 집계에 `exclude` 전달(이벤트·tier 입력은 그대로).
   - `routes/root_learning.py` `overview_data`·`project_session`, `server/app/lecture_mastery.py`, `server/app/routes/study_plan.py`에서 사용자 값 읽어 전달.
3. 서버 검사: `server/tests/test_root_optional_exclusion.py` 새로(꺼짐=기존 값, 켜짐=Optional 제외, 내 중요도 반영, 전부 Optional이면 None, availability·plan 불변, 같은 requestId 1회), `test_route_contract.py`에 경로 추가.
4. 웹: `web/src/bank/optionalExclusion.ts`(값 읽기·저장·변경 알림), `StudyOverview.tsx` 버튼·`overview.css`,
   변경 시 무효화 — `useRootCatalog.ts` 60초 캐시, `calendar/useCalendarTimetable.ts`, `useMainQuizEntry.ts`, `EventPanel.tsx` 패널 진척, `useTodayPlan.ts`.
5. `docs/map.md` 한 줄, 대시보드 범위 갱신.

## 검사 명령과 성공 조건
- `server/`에서 `.venv/Scripts/python.exe -m tests root` 및 전체 `-m tests` 통과(기존 결함은 따로 표시).
- `npm --prefix web run typecheck`, `npm --prefix web run build` 통과.
- 로컬 격리 DB로 서버·웹을 띄워 토글 전후 강의 목록·캘린더·패널 수치가 바뀌고, 다시 끄면 원래 값인지 브라우저로 확인. 운영 DB는 쓰지 않는다.
- PR CI `Tests and build` 통과.

## 위험·복원·승인할 범위
- 위험: 집계 함수에 실수가 있으면 꺼짐 상태 학습률이 달라질 수 있음 → 꺼짐 = 기존 값 테스트로 막음. 풀이·계획 경로는 건드리지 않음.
- 복원: PR revert. 저장된 `kind='optional'` 이벤트는 남아도 다른 기능이 읽지 않는다.
- 승인 요청 범위: 위 파일의 로컬 구현·검사·PR 생성까지. master 병합(=운영 자동 배포)은 따로 승인받는다.
