# Make CI tests reproducible from a clean checkout — 배포 준비

## 코드 리뷰·검증 결과
CI 수집 실패의 두 원인을 수정했다. 일반 metrics/quality_checks 함수는 기존 읽기 전용 구현 그대로 추적 모듈에 보존했고 테스트가 이를 import한다. requests를 CI 검사 의존성으로 명시했다. 관련 25개 로컬 검사와 Git 추적 파일만 복제한 work 없는 checkout의 동일 25개 검사를 모두 실행해 통과했다. 제품 서버/웹 코드와 운영 데이터는 변경하지 않았다.

## 배포 대상 버전·순서·데이터 변경
이번 작은 복구 commit을 origin/master에 push하고 동일 SHA의 GitHub 전체 검사와 기존 자동 배포를 확인한다. 최초 run 41982881963의 실패를 보존하며 검사 생략/성공 위장은 하지 않는다. 새 checkout에서 실행되는 CI가 최종 전체 회귀 근거다.

## 배포 후 확인·롤백·필요한 사람 승인
현재 사용자의 Git 보존·push·자동 배포 요청과 명시적 추가 권한 승인을 같은 범위에 적용한다. 클라우드 권한 추가 변경은 없다. GitHub/Pages 최종 SHA와 API revision/401을 읽어 확인하고 실행 영수증을 로컬 runs와 Actions artifact에 보존한다. 복원은 이 작은 commit의 revert 및 기존 협업 안내를 따른다.

두 번째 원격 실행 41983410862는 Python 1,919 passed/1 skipped/1 failed였다. 남은 실패는 Windows 바로가기 설치 검사가 요구하는 .venv 부재다. CI에 실제 프로젝트 가상환경 생성과 PATH 등록을 추가했다. 기존 바로가기 검사를 포함한 로컬 검사를 다시 통과했으며 새 SHA에서 전체 CI를 실행한다. 기존 원격 실패를 보존하고 건너뛰기로 해결하지 않는다.

run41984679415에서 실제 오류를 확인: 영어 Windows WScript.Shell.Save가 `Study EZ ??.lnk`를 저장하지 못했다. 같은 목적지에 고유 ASCII 임시 이름으로 COM 저장 후 PowerShell Unicode Move-Item으로 원래 이름을 반영하며 임시 파일을 finally 정리하도록 installer를 수정했다. 대상 pythonw/인수/설명/작업 디렉터리는 유지한다. 기존 테스트에 임시 파일 잔여 없음 검증과 실패 출력만 보강했다. 관련 38개 로컬 검사와 PowerShell UTF-8 BOM 보존을 확인했다. 영문 Windows의 실제 동작은 새 GitHub SHA에서 검증한다.

run41985032273: 영어 Windows installer와 전체 Python 회귀 통과. 서버는106/107 통과, 기존 시간표 조건부 도구 입력 timetable-patch.json/source.json이 ignore되어 누락된 한 건만 실패했다. 두 정확한 입력 경로만 추적하고 해당 정본에 -text를 적용해 원래 승인 CRLF 바이트를 보존했다. 기존 source after_sha256를 변경하지 않았고 staged blob의 SHA가 원래 승인 값과 정확히 일치함을 검증했다. 로컬 및 Git 추적 파일만 새로 복제한 checkout에서 시간표 보존/재실행/복원/실패 원자성 6개 시나리오 모두 통과. 실제 운영 DB 갱신·PDF 추가·문항 변경은 없다.
