# Git collaboration snapshot and automatic production deployment — 구현 계획

## 변경 범위·대상 파일·순서
1. 현재 Git 대상 파일 목록/크기를 점검하고 민감 경로·비밀 패턴을 점검한다.
2. .github/workflows/deploy.yml, scripts/ci_deploy.py, web/scripts/wait-for-api.mjs, health revision과 격리 검사를 추가한다. workflow_scope에 .github 입력을 추가한다.
3. 전체 계약/루트 회귀/서버 독립 검사/웹 빌드/자동 배포 실패 검사를 실행하고 release.md와 review를 기록한다.
4. 전용 Google 서비스 계정 및 저장소/master/workflow 제한 OIDC를 만들고 GitHub 공개 설정 변수만 등록한다. Cloudflare 빌드 명령을 API SHA 대기 후 웹 빌드로 바꾼다. 기존 설정 백업은 runs/_development 아래 로컬 보관한다.
5. 기존 변경 스냅샷과 이번 자동 배포 변경을 명확한 커밋으로 남기고 origin/master 푸시한다. Actions와 Pages의 실제 SHA·배포·읽기 사후 검사를 확인한다.

## 검사 명령과 성공 조건
contracts: .venv/Scripts/python.exe -m pytest tests/contracts -q
server: server/.venv/Scripts/python.exe -m tests (server cwd, 파일별 독립)
web: npm.cmd --prefix web run build
automation: 자동 배포 스크립트의 가짜 cloud 실패/소스 변경/잘못된 SHA·트래픽 검사와 웹 대기 스크립트의 불일치/시간 초과/정상 검사
regression: .venv/Scripts/python.exe -m pytest tests -q 및 bridge Node 검사. 실패/미실행을 구별하고 이번 범위 밖 기존 실패는 원인을 보고한다.

## 위험·복원·승인할 범위
사용자 현재 요청은 위 Git 보존·push·일반 코드 자동 배포 설정 및 검증을 승인한다. 실제 변경은 이 범위로 제한한다. 복원: Actions disable/Cloudflare production 자동 배포 중지 후 이전 Cloud Run revision으로 트래픽 복원 및 이전 Pages deployment rollback. 원격 강제 푸시·기존 이력/자료 삭제는 하지 않는다. GitHub branch protection 불가를 문서에 명시한다.
