# Make CI tests reproducible from a clean checkout — 구현 계획

## 변경 범위·대상 파일·순서
기존 work helper의 read/jsonl/metrics/quality_checks 일반 함수를 scripts/incremental_comparison.py에 의미 변경 없이 복사한다. 테스트는 추적 모듈을 import한다. .github/workflows/deploy.yml의 검사 설치 목록에 requests를 추가한다. 로컬 격리 체크 후 commit/push하고 새 GitHub 전체 실행/배포를 확인한다.

## 검사 명령과 성공 조건
automation: pytest tests/quizbank/test_incremental_comparison.py tests/development/test_ci_deploy.py -q. 추가로 추적된 파일만 임시 checkout에 복제하여 work 없이 같은 검사를 실행한다. 새 SHA의 전체 Python/서버/웹/Node 검사는 GitHub Actions가 실제 실행한다.

## 위험·복원·승인할 범위
사용자의 현재 자동 배포 구현·연결·검증 승인에 포함되는 clean checkout 검사 복구다. 모델 재호출/내용 승인/자료 이동/기존 work 수정은 없다. 복원은 이 작은 commit revert이며 기존 데이터 보존을 유지한다.
