# Make CI tests reproducible from a clean checkout — 구현 계획

## 변경 범위·대상 파일·순서
기존 work helper의 read/jsonl/metrics/quality_checks 일반 함수를 scripts/incremental_comparison.py에 의미 변경 없이 복사한다. 테스트는 추적 모듈을 import한다. .github/workflows/deploy.yml의 검사 설치 목록에 requests를 추가하고 실제 개발 구조와 같은 .venv를 만든 뒤 이후 단계 PATH에 등록한다. 로컬 격리 체크 후 commit/push하고 새 GitHub 전체 실행/배포를 확인한다.

원격 Windows 진단으로 WScript.Shell.Save가 영어 시스템의 한글 .lnk 파일명에서 FileNotFoundException을 발생시킴을 확인했다(run41984679415). scripts/install-runner-desktop.ps1은 같은 목적지의 고유 ASCII 임시 .lnk로 COM 저장 후 PowerShell Unicode Move-Item으로 원래 한글 이름에 반영하고 임시 파일을 정리한다. 기존 shortcut 테스트에서 최종 파일과 임시 파일 정리도 확인한다. 실제 협업 환경 재현성 수정이며 러너/생성/업로드 동작은 바꾸지 않는다.

run41985032273의 Python 회귀는 통과했고 서버106/107 통과, timetable-patch.json 누락 한 건이 남았다. 기존 조건부 시간표 도구가 실제 입력으로 사용하는 timetable-patch.json/source.json 두 파일만 .gitignore 예외로 보존한다. source.json의 승인된 after_sha256과 같은 원래 CRLF 바이트를 Git에서도 보존하도록 .gitattributes에 해당 시간표 한 파일의 -text 예외를 추가한다. JSON 내용·기존 해시·패치·시간표 의미는 바꾸지 않는다. 새 복사본의 입력 해시/격리 DB의 시간표 보존·복원 검사를 검증한다.

## 검사 명령과 성공 조건
automation: pytest tests/quizbank/test_incremental_comparison.py tests/development/test_ci_deploy.py -q. 추가로 추적된 파일만 임시 checkout에 복제하여 work 없이 같은 검사를 실행한다. 새 SHA의 전체 Python/서버/웹/Node 검사는 GitHub Actions가 실제 실행한다.

## 위험·복원·승인할 범위
사용자의 현재 자동 배포 구현·연결·검증 승인에 포함되는 clean checkout 검사 복구다. 모델 재호출/내용 승인/자료 이동/기존 work 수정은 없다. 복원은 이 작은 commit revert이며 기존 데이터 보존을 유지한다.
