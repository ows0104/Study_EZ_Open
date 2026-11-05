# 감염과 면역 예습의 하위 폴더 필기 탐색 누락 — 구현 계획

Implementation Plan. 현재 대화에서 하위 폴더·준비 판정 수정과 내일 예습 재실행을 명시적으로 승인받았다.

1. runner/filenames.py의 연도 하위 폴더 탐색을 수정하고 링크·충돌·중복·최신 판·연도 혼입 회귀를 검사한다.
2. 하위 경로를 사용하는 publish/prequeue/watch 소비자의 경로·매칭 계약을 검증한다.
   run ID 배정은 filenames.py로 공유하고 watch의 기존 진입점은 유지한다.
3. runner/readiness.py에 생성·파일 쓰기 없는 로컬 자료/확정 매칭 조회를 추가하고
   scripts/runner_desktop_jobs.py의 링크 준비와 실행 가능한 상태를 구분하는 표시를 보강한다.
   내일 TBL은 두 작년 강의가 합쳐진 시간표이므로 원본 두 PDF를 보존한 합본 입력과 출처/해시를
   runs/_materials에 만들고 명시적 확인 매칭으로 연결한다. readiness/publish는 이 검증된 입력을 함께 읽는다.
   합본의 작업 ID는 실제 원본 강의 ID와 구분한 파생 입력 ID로 기록한다. 원본 폴더에 파일을 추가하지 않는다.
4. tests/runner 관련 회귀와 전체 검사, 격리 DB/데스크톱 검사를 실행하고 revision-bound 리뷰/릴리스를 기록한다.
5. 검사/리뷰 후 현재 러너를 안전하게 최신 코드로 연결하고 11월 3일 예습만 force 없이 재등록·실행 확인한다.
   원본과 기존 작업/검수 이력을 보존한다. 링크가 없는 강의의 웹 생성은 하지 않는다.
   실제 재실행에서 uv Python 프록시의 하위 PDF 도구 실행이 거절되어, runner/desktop.py의
   실행 환경 선택을 기존 scripts/agent.ps1과 같은 Anaconda/Miniconda 우선순위로 맞춘다.
   보안 설정·권한·검수 규칙은 바꾸지 않고 이미 설치된 정상 실행 환경으로 같은 시도를 재개한다.

복원은 변경 코드 되돌리기다. 원본 PDF나 runs 기록은 이동·삭제하지 않는다. 서버 배포는 필요 여부를 별도 판단한다.
