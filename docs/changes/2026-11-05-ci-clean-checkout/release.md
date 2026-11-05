# Make CI tests reproducible from a clean checkout — 배포 준비

## 코드 리뷰·검증 결과
CI 수집 실패의 두 원인을 수정했다. 일반 metrics/quality_checks 함수는 기존 읽기 전용 구현 그대로 추적 모듈에 보존했고 테스트가 이를 import한다. requests를 CI 검사 의존성으로 명시했다. 관련 25개 로컬 검사와 Git 추적 파일만 복제한 work 없는 checkout의 동일 25개 검사를 모두 실행해 통과했다. 제품 서버/웹 코드와 운영 데이터는 변경하지 않았다.

## 배포 대상 버전·순서·데이터 변경
이번 작은 복구 commit을 origin/master에 push하고 동일 SHA의 GitHub 전체 검사와 기존 자동 배포를 확인한다. 최초 run 41982881963의 실패를 보존하며 검사 생략/성공 위장은 하지 않는다. 새 checkout에서 실행되는 CI가 최종 전체 회귀 근거다.

## 배포 후 확인·롤백·필요한 사람 승인
현재 사용자의 Git 보존·push·자동 배포 요청과 명시적 추가 권한 승인을 같은 범위에 적용한다. 클라우드 권한 추가 변경은 없다. GitHub/Pages 최종 SHA와 API revision/401을 읽어 확인하고 실행 영수증을 로컬 runs와 Actions artifact에 보존한다. 복원은 이 작은 commit의 revert 및 기존 협업 안내를 따른다.
