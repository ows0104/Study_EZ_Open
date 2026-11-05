# Git collaboration snapshot and automatic production deployment — 설계

## 요구사항과 수용 기준
1. 모든 현재 Git 추적 대상 변경을 비밀값 점검 후 커밋하고 강제 푸시 없이 origin/master에 푸시한다.
2. GitHub Actions는 PR/master push를 검사한다. 검사 실패는 서버 배포를 막는다. 배포는 master push/현재 master 수동 재실행에 한정한다.
3. Google OIDC는 해당 저장소 ID·소유자 ID·master·배포 workflow에 한정한다. 장기 서비스 계정 키나 운영 DB 비밀을 GitHub에 복사하지 않는다.
4. 서버 소스는 기존 allowlist 패키지만 배포하고 기존 환경/Secret Manager 참조를 보존한다. 유일한 새 환경값 STUDYEZ_REVISION은 공개 Git SHA이다. 무트래픽 revision 생성→Ready 확인→정확한 revision 100% 전환→health SHA/인증 관문 읽기 검사를 기록한다.
5. Cloudflare 기존 Git 연결을 유지하되 preview 자동 배포를 끈다. master 웹 빌드는 자신의 CF_PAGES_COMMIT_SHA와 API health revision이 일치할 때만 진행한다. 제한 시간 내 불일치/장애는 실패다. 새 Pages API 키가 필요 없다.
6. 협업/복원/일반 자동 코드 배포와 별도 운영 데이터 변경의 경계를 문서화한다. 검사와 배포 영수증은 Git SHA·패키지 해시에 묶어 Actions artifact에 보관한다.

## 책임·입출력 계약·오류 상태
API health에 비밀이 아닌 revision 필드를 추가한다. 기존 status/environment를 유지한다. 자동 배포 스크립트는 GitHub Actions 환경·repository·ref·현재 원격 master와 source artifact 해시를 확인한다. 이전 revision과 새 revision, 사후 검사 결과를 기록하며 실패를 성공으로 바꾸지 않는다. 배포 concurrency는 취소 없이 직렬화하여 트래픽 전환 도중 강제 중단하지 않는다.

## 호환성과 데이터 보존
DB migration/init-db·콘텐츠 생성/교체·학습 기록 변경·비밀키 회전·Spotter 정적 사이트 배포는 수행하지 않는다. 기존 중요 운영 승인 정책은 이 범위 밖에서 유지한다. 현재 사용자의 자동 배포 요청을 일반 코드 master 배포의 승인 근거로 명시하며 이후 작업의 구현 승인으로 확대하지 않는다.
