# 검증된 최신 master 서버·웹 운영 배포 — 구현 계획

## 변경 범위·대상 파일·순서
1. 현재 운영 버전과 DB 호환성을 읽기 전용으로 확인하고 복원 기준을 기록한다.
2. 격리 서버 전체 검사, 웹 운영 빌드 및 공통 계약 검사를 현재 사이트 지문에 연결한다.
3. allowlist 서버 패키지와 검증된 web/dist를 고정 후보로 준비하고 리뷰한다.
4. 현재 사용자의 서버·웹 최신 버전 배포 지시에 근거해 후보별 중요 배포 승인을 기록한다.
5. 기존 deploy.ps1로 서버의 새 버전을 준비한 뒤 100% 전환 및 사후 검사를 확인한다.
6. 고정 웹 후보를 Cloudflare에 게시하고 실제 배포 ID와 정적 파일 일치를 확인한다.
7. 읽기 전용 학습 화면과 HTTP 검사를 확인하고 배포 영수증·한계를 남긴다.
문제 내용·학습 기록 변경이나 별도 인증 권한 확대는 범위에 포함하지 않는다.

## 검사 명령과 성공 조건
server/.venv의 scripts/check_server_release.py, root .venv의 scripts/check_web_release.py,
pytest tests/contracts를 development.py verify의 server/web/contracts로 실행한다.
실제 성공 수·로그와 최신 지문을 확인하고 후보별 release/deploy gate를 통과해야 한다.

## 위험·복원·승인할 범위
새 버전의 Ready·100% 트래픽·실제 운영 파일을 확인한다. 실패 시 기존 배포를 성공으로 오인하지 않는다.
이전 API studyez-api-00171-9wx 및 Pages 0fbb9e8b 배포로 복원할 수 있다. 파괴적 DB 작업은 없다.
사용자의 현재 사이트 최신 배포 요청은 이 서버·웹 배포와 필요한 설정 유지·후보 준비를 포함한다.
