# Main-Quiz 요약 빠르게(시작 때 가벼운 사본) — 구현 계획

## 변경 범위·대상 파일·순서
1. `server/app/root_learning/light.py` — `_load_lock`·`_load`·`warm`, LIMIT 64.
2. `server/app/main.py` — `warm_main_quiz`, `lifespan`(운영만).
3. `server/tests/test_root_light.py` — 6·7번: 미리 만들기 뒤 첫 목록 요청은 원본 0번, lifespan 함수 자체,
   동시 4요청 원본 1번(잠금을 빼면 4번으로 실패하는 것 확인), 실패 강의는 건너뛰고 다음 번엔 만든다.

## 검사 명령과 성공 조건
- `server/.venv/Scripts/python.exe -m tests root` — `root_light` 포함 통과. `root_map_tree*` 2건은 이 venv에 pymupdf가 없어 import에서 멈춤(이전 작업 기록과 같은 환경 문제).
- `-m tests timetable` 통과. ruff F: 바꾼 코드 깨끗(시험 파일의 미사용 import 3개는 master에도 있음).
- 배포 뒤: Cloud Run 로그의 시작 메시지(편수·초), `GET /api/root-learning` 지연(배포 직후 포함), 「Memory limit」 재발 여부.

## 위험·복원·승인할 범위
- 위험: 새 인스턴스 시작이 수 초 늦다. DB가 느리면 시작이 그만큼 늦다(실패해도 서버는 뜬다).
- 복원: `STUDYEZ_WARM_MAIN_QUIZ=0` 또는 git revert / 이전 Cloud Run revision. 데이터 변경 없음.
- 승인 범위: 사용자 요청 원문의 숫자 칸 채우기 — 위 서버 파일과 검사. DB 스키마 변경 없음.
