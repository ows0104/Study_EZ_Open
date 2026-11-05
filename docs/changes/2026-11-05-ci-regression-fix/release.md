# Fix equal-metadata deck promotion and restore deployment — 배포 준비

## 코드 리뷰·검증 결과
수정 전 결정적 회귀 검사: 같은 크기·같은/이전 mtime의 다른 내용 2건과 같은 내용·새 mtime 보존 1건이 실패했다(3 failed, 15 passed). 수정 후 promote 전체 18개, 계약 125개, 전체 회귀 1923 passed / 1 skipped 통과. 전체 회귀 검사와 PR CI 결과는 state.json 및 해당 커밋의 Actions에 보존한다. 첫 전체 로컬 실행은 긴 Windows 임시 경로로 실패하여 중단했다. 짧은 임시 경로를 사용한 다음 실행에서 작업 사본의 .venv/pyvenv.cfg 부재 및 기존 Python의 Tk 라이브러리 경로 오류가 확인됐다(1 failed, 1920 passed, 1 skipped, 2 errors). 기존 설정을 작업 사본에 복사하고 설치된 Python 3.13.5의 TCL_LIBRARY/TK_LIBRARY를 지정한 뒤 해당 환경 검사 15개와 최종 전체 검사를 통과했다. 운영 코드나 검사 기준은 환경 문제를 이유로 변경하지 않았다.

리뷰 범위: 덱 선택, CHOSEN, 구형 폴더 처리, 누락 오류는 유지한다. 같은 크기일 때만 두 파일을 열고 스트리밍 SHA-256을 비교한다. 양쪽 핸들은 복사 전에 닫힌다. 같은 내용이면 목적지 mtime을 보존한다. 새 의존성·전역 비교 캐시·임의 대기·검사 생략이 없다. 비용은 같은 크기 파일 두 개를 순차 읽는 I/O다.

## 배포 대상 버전·순서·데이터 변경
대상은 codex/ci-regression-fix의 리뷰된 커밋을 병합한 master SHA다. 실제 고정 SHA 및 테스트 후보 해시는 GitHub Actions의 server-<sha>, deployment-<sha>-<attempt> 영수증으로 확인한다. docs/development/collaboration.md의 승인된 자동 배포 경로를 사용한다: PR 검사 → merge → master 검사 → 동일 실행의 고정 API 후보 배포 → API SHA 확인 후 Cloudflare Pages 웹 배포. DB migration, 운영 데이터, 문항 내용, 학습 기록, 비밀값 및 권한 변경은 없다. 로컬 러너 재시작도 하지 않는다.

## 배포 후 확인·롤백·필요한 사람 승인
사용자 승인(2026-11-05 현재 채팅): “그럼 dashboard 규칙대로 실패 원인 확인하고 수정해서 배포까지 진행해줘.” 이 수정의 구현·검사·PR merge·일반 코드 자동 배포에 적용한다. 수동 후보 배포를 실행하지 않으며 기존 자동 배포의 SHA별 검사·영수증을 보존한다. 성공은 master Actions의 실제 배포 성공, 운영 /api/health revision 일치, 보호 API의 401 및 Cloudflare의 해당 SHA 성공을 확인한 뒤에만 보고한다. 최종 결과·링크는 dashboard 완료 기록과 이 작업의 로컬 사후 확인에 남긴다. 실패 시 우회 배포 없이 원인을 확인한다. 회귀가 있으면 이 수정의 revert PR로 복원하고, 트래픽 복원이 필요하면 영수증의 previous_traffic을 사용한다. 데이터는 되돌리지 않는다.
