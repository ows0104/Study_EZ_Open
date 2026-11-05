# Make CI tests reproducible from a clean checkout

## 문제와 사용자 효과
사용자의 현재 Git 전체 보존·push·자동 배포 요청 및 추가 자동 배포 연결 승인 범위에서 새 checkout에서도 검사 가능하게 한다. 최초 GitHub run 41982881963은 기존 검사가 Git에서 제외된 work.incremental-review-20261015.compare_next_job를 import하고 Spotter 검사 requests 의존성이 빠져 수집 단계에서 실패했다. 운영 배포는 실행되지 않았다.

## 범위와 성공 기준
검사에 필요한 일반 읽기 전용 metrics/quality_checks 함수만 추적 가능한 scripts/incremental_comparison.py로 보존하고 검사 import를 바꾼다. CI 검사 의존성 requests를 명시한다. 원본 work 실행 도구/자료/운영 상태는 변경하지 않는다.

## 근거·미정 사항
초기 로컬 1,921개 검사는 기존 PC 파일/설치가 있어 통과했지만 clean checkout 검증을 대신하지 못했다. 실패 기록을 보존하고 새 SHA에서 GitHub 전체 검사를 다시 실행한다.
