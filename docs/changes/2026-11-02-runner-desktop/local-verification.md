# Local verification — 2026-11-02 KST

- 사용자가 전체 일시정지는 진행 중 작업도 멈추고 재개 시 이어 처리하는 방식임을 확인했다.
- 전체 498개 검사 통과: 비화면 488, 새 화면 8, 기존 상태 창 2. 별도 desktop 21개와 격리 DB 검사 통과.
- `development.py check --phase release`: ready=true. 현재 revision-bound 근거는 state.json 참조.
- `C:\Users\ows01\Desktop\Study EZ 러너.lnk` 설치 완료.
  대상은 기본 설치의 실제 pythonw.exe, 인수는 `-m runner.desktop`, 작업 폴더는 이 저장소다.
- `Study EZ 러너` 창과 백그라운드 러너가 실행 중이며 desktop.log에 오류가 없다.
- 실제 서버 조회: 강의/예습/복습 작업 행 162개. 신규 자동 시작 가능 0개.
  기존 실패 8건은 자동 재실행하지 않았다.
- 실행/대기 작업이 없는 유휴 상태에서 전체 일시정지 설정과 전체 재개를 실제 어댑터로 확인했다.
  최종 `runs/desktop-control.json`의 paused=false로 원래 실행 상태를 복원했다.
- 실제 하위 프로세스 중단과 산출물 보존은 운영 강의가 아닌 격리된 child/checkpoint 검사로 검증했다.
- Computer Use에서 창 검색은 성공했으나 화면 캡처 접근 확인이 시간 초과했다. 시각 검증은 미완료다.
- 서버/웹 배포, DB 스키마, 로그인 예약 작업, 강의 원문/문항/학습 기록 변경 없음.

Maintain: 강의별 시작은 기존 자료/검수 조건을 재확인한다. 중지·취소·전체 일시정지는 로컬 설정과
서버 확인 상태를 구분하여 표시한다. 자동화가 실패/취소된 항목의 검수 상한을 초기화하지 않는다.
