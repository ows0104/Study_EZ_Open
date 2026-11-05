# Git collaboration snapshot and automatic production deployment — 배포 준비

## 코드 리뷰·검증 결과
계약 125개, 자동 배포 실패 경로 19개, 서버 독립 파일 107개, 웹 타입/빌드, bridge+웹 gate Node 95개와 구조 검사를 실행했다. 전체 Python 회귀는 1,921개다. 초기 실패에는 제한된 임시 폴더 권한/Windows 경로 길이/혼합 Python 표준 라이브러리/uv Tcl 설치 누락이 있었다. 정상 권한·짧은 임시 경로·서버 환경 초기화로 서버 검사를 통과했다. 최종 회귀는 1,919개를 루트 런타임으로, 상태창 2개를 정상 Tcl 설치가 있는 서버 런타임으로 분리 실행한다. 실패 기록과 실제 최종 종료 코드는 state.json과 로컬 로그에 보존한다. CI는 공식 Windows CPython 3.13으로 전체를 실행한다.

검토: PR에 배포 권한 없음, OIDC repository/master/workflow 제한, 현재 원격 head 확인, 같은 실행의 후보 파일 해시 확인, 기존 환경/Secret Manager 참조 보존, 무트래픽 revision 준비와 정확한 100% 전환 확인, 읽기 health SHA/401 확인, 실패 영수증, Pages SHA 불일치/장애 시 게시 중단을 확인했다. private branch protection은 현 요금제로 불가(403)하며 강제 보호로 보고하지 않는다.

최종 로컬 결과: 루트 1,919 passed + 상태창 2 passed = 1,921개 모두 통과. 서버 107개 모두 통과. `development.py check --phase release` ready=true 확인. 원래 검사 실패를 삭제하거나 성공으로 수정하지 않았다.

## 배포 대상 버전·순서·데이터 변경
대상은 origin/master의 이번 스냅샷과 `.github/workflows/deploy.yml`이다. 코드 지문은 state.json에 고정하며 실제 Git SHA는 push 후 Actions가 동일 실행에서 패키지 해시와 함께 고정한다. 기존 미커밋 source/테스트/작업 문서를 사용자 요청으로 함께 보존한다. 비밀값·원본 강의·생성 실행물은 기존 Git 제외 규칙을 따른다. 저장소는 계속 private다.

Git push 전에 로컬 release gate를 확인한다. push 후 동일 SHA의 Actions 검사→고정 서버 후보→무트래픽 revision 생성/Ready→정확한 100% 트래픽→읽기 health SHA/401을 검증한다. Pages는 같은 SHA API를 최대 15분 기다리고 웹 빌드 직후 다시 확인한 뒤 배포한다. DB migration/init-db, 콘텐츠 생성·은행 교체·학습 기록/공개 권한 변경은 없다. Spotter 정적 사이트나 로컬 러너 설치도 수행하지 않는다.

## 배포 후 확인·롤백·필요한 사람 승인
현재 사람의 자동 배포 요청과 추가 권한 승인은 authorization.md에 원문과 범위를 보존한다. Google 계정은 소스 배포/service usage 역할과 기존 runtime 계정 actAs만 부여하고 OIDC는 저장소 ID/소유자 ID/master/해당 workflow로 제한한다. 장기 키·DB/R2/runner 비밀은 GitHub에 등록하지 않았다. GitHub 변수 두 개와 Cloudflare build 명령/preview 중지/Node 24/기존 로그인 도메인 보존을 확인했다.

실제 실행/배포 ID와 응답 확인 결과는 Actions 영수증 및 로컬 runs/_development/2026-11-05-git-autodeploy에 기록한다. 배포 성공은 push 성공과 구분한다. 복원은 협업 안내의 이전 Cloud Run 트래픽/Pages 배포 복원을 따르며 자동 강제 롤백·force-push는 없다. Pages 20분 전체 제한 내 API 배포가 끝나지 않으면 웹은 실패하며 같은 SHA를 Retry한다.
