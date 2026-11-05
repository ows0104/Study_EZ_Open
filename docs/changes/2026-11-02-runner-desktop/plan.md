# 창 없는 러너 프로그램과 1분 자동 시작 — 구현 계획

사용자의 현재 명시적 구현 승인을 아래 범위에 적용한다. 같은 승인을 다시 요청하지 않는다.

1. runner/desktop_control.py: 60초 대기 상태, 로컬 일시정지·강의별 중지/취소 파일과 조작 직렬화.
2. scripts/runner_desktop_jobs.py: 기존 서버 런타임·러너 인증·큐 정책을 재사용하는 로컬 작업 조회/조작.
   서버 코드는 변경/배포하지 않는다. runner/agent.py에 로컬 제어 확인과 보류/재개를 연결한다.
   runner/publish.py는 중지·취소한 갈래의 덱이 주기적 업로드로 우회 반영되지 않게 보류한다.
3. runner/desktop.py: 기존 StatusWindow를 재사용하는 강의별·갈래별 시작·중지·취소와 전체 일시정지 UI.
   runner/status_window.py에는 상태 전용 동작을 유지하는 작은 확장 지점만 추가한다.
4. scripts/install-runner-desktop.ps1: 기본 pythonw와 작업 폴더를 지정하는 바탕화면 바로가기.
5. tests/runner/test_desktop*.py, server/tests/test_runner_desktop.py: 시간·취소·오류·중복 실행·중지 안전성,
   강의/갈래 격리·자료 준비·자동 상한과 격리된 GUI/로컬 DB 검증.
   development.py verify의 runner 검사는 tests/runner 전체, desktop 검사는 신규 GUI/제어 검사,
   desktop-db 검사는 server 런타임의 격리 DB 작업 검사를 실행한다.
6. 코드 리뷰·release.md와 로컬 완료 근거를 남기고 바로가기를 설치하여 프로그램을 연다.
   현재 작업을 확인하고 일감이 없는 안전한 시점에 새 제어를 지원하는 러너로 교체한다.

복원: 추가한 바로가기를 제거하고 기존 runner-status.ps1을 사용한다. 데이터와 서버 배포는 변경하지 않는다.
로그인 예약 작업은 변경하지 않는다. 중요 운영 배포 대상이 아닌 로컬 도구 설치다.
