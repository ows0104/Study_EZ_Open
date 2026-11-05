# 러너 현재 블럭 화면과 이전 기록 분리 — 구현 계획

1. runner/history.py에 현재 화면 분리·지난 기록 수집·추가 JSON 보관을 구현한다.
   status.py/status_batch.py/status_external.py에 선택적 과목 정보를 보존해 같은 ID의 다른 과목을 구별한다.
2. scripts/runner_desktop_jobs.py에 인증/읽기 전용 트랜잭션을 유지하는 전체 과거 작업 조회를 추가한다.
3. runner/desktop.py에 기본 화면 범위 제한과 이전 블럭 기록 창을 연결한다. 유지보수 재개창은 자동 시작을 재설정하지 않는다.
4. tests/runner의 범위/보관/GUI 회귀와 server/tests/test_runner_desktop.py의 격리 DB 전체 기록 조회를 검사한다.
   development.py의 runner 및 desktop-db 검증에 기록한다.
5. 실제 과거 기록 조회본을 저장하고 원본 유지·현재 작업 유지·첫 화면 분리를 확인한다.
   프로그램 창만 안전하게 갱신하고 기존 생성기/러너는 유지한다. 코드 리뷰와 로컬 release gate를 기록한다.

사용자의 현재 요청을 이 범위의 build/로컬 반영 승인으로 적용한다. 서버 배포·DB 변경·물리적 원본 보관 이동은 없다.
복원은 UI 코드 원복이다. 추가 조회본과 원본 기록은 삭제하지 않는다.
