# 공동작업과 자동 배포

2026-11-05 사용자 요청으로 `master` 코드 변경의 자동 배포를 활성화한다. 이번 요청은
일반 코드 배포 자동화의 승인 근거이며, 새 기능의 구현 승인이나 운영 데이터 변경 승인을 대신하지 않는다.

## 작업 방법

1. 최신 master에서 개인 브랜치를 만든다. 에이전트 기본 접두사는 `codex/`다.
2. `docs/changes/<id>/`에서 intent → spec → plan과 실제 사람의 구현 승인 근거를 보존한다.
3. 변경을 push하고 master 대상 PR을 만든다. `Tests and build` 결과와 코드 리뷰를 확인한다.
4. master 병합/push 후 검사가 다시 통과하면 API를 먼저 배포한다. 웹은 같은 Git SHA가
   운영 API `/api/health`에 표시된 후 빌드하고 업로드한다.
5. [Actions](https://github.com/ows0104/Study_EZ_Open/actions/workflows/deploy.yml)와
   Cloudflare Pages에서 최종 성공 여부를 확인한다. Git push 성공은 배포 성공과 다르다.

private 저장소의 현재 GitHub 요금제에서는 브랜치 보호 API가 403을 반환한다.
필수 PR/검사/승인 강제 보호는 설정되지 않았다. 협업자는 위 절차를 지켜야 하며, 요금제 변경 시
master 직접 push 금지·필수 검사 `Tests and build`·리뷰 승인을 설정할 수 있다.

## 자동으로 실행되는 범위

`.github/workflows/deploy.yml`은 PR/master push/수동 실행에서 Windows Python 회귀, 독립 서버 검사,
웹 타입/빌드, bridge 및 배포 실패 경로 검사를 실행한다. master만 배포 권한을 얻는다.
검사 작업에서 고정한 서버 패키지와 해시를 동일 실행의 배포 작업에 전달하고 Git SHA·실행 ID·파일 해시를
재확인한다. 다른 커밋으로 master가 전진했으면 이전 작업은 배포를 중단한다.

Google OIDC provider는 저장소 ID `1335642658`, 소유자 ID `37865114`,
`refs/heads/master`, 이 배포 workflow의 master 실행만 신뢰한다. 전용 서비스 계정은 source 배포 역할과
기존 runtime service account의 actAs만 사용한다. GitHub에는 provider/계정 이름 변수만 저장하며
DB/R2/runner 비밀이나 서비스 계정 JSON 키는 저장하지 않는다.

Cloud Run은 기존 환경/Secret Manager 참조를 보존하고 공개 Git SHA인 `STUDYEZ_REVISION`만 추가한다.
새 revision을 무트래픽으로 생성하고 Ready/ContainerReady·최신 생성 버전을 확인한 후 그 revision으로만
100% 전환한다. health SHA와 무인증 보호 경로의 401을 확인하고 이전 트래픽/새 버전/검사 결과를
Actions `deployment-<sha>-<attempt>` artifact에 30일 보관한다. 테스트 후보는 14일 보관한다.

Cloudflare Pages는 기존 Git 연결과 웹 환경값을 유지한다. 빌드 명령은 `npm run build:pages`,
root는 `web`, output은 `dist`, production branch는 `master`, preview 자동 배포는 끈다.
Pages는 최대 15분 동안 같은 SHA의 운영 API를 기다리고 웹 빌드 후 다시 확인한다. 실패하면 게시하지 않는다.
Cloudflare의 전체 빌드 제한은 20분이므로 장시간 검사/Cloud Build 대기 시 Pages 빌드가 실패할 수 있다.
API가 확인된 뒤 해당 SHA의 Pages 배포를 Retry한다. Pages가 다른 SHA를 배포했는지 확인한다.

## 별도 승인이 필요한 작업

DB migration/init-db, 문항/은행 교체, 사용자 학습 기록, 공용 권한·비밀값 회전, 자료 이동/삭제는
자동 배포가 실행하지 않는다. 해당 작업의 보존 정책과 중요 운영 승인을 따르고 DB 호환 준비를 먼저 마친다.
자동 배포되는 코드는 이전 웹/러너와 호환돼야 한다. Spotter 정적 배포와 로컬 러너 설치/재시작도 별도다.
기존 `development.py`/`release_evidence.py`의 수동 고정 후보 경로는 유지하며, 이번 일반 코드 자동 경로는
이 문서와 GitHub 실행의 SHA별 검사/배포 근거로 기록한다. CI가 사람의 승인 발언을 만들어 기록하지 않는다.

## 실패와 복원

트래픽 전환 전 실패는 이전 서버가 계속 처리한다. 전환 후 사후 검사 실패는 실패 영수증을 남기며
자동 복원하지 않는다. `previous_traffic`의 revision을 확인해 승인된 복원을 실행한다.

```powershell
gcloud run services update-traffic studyez-api --project meddeck-503318 --region asia-northeast3 --to-revisions <이전_revision>=100
```

코드 복구는 `git revert` PR로 남긴다. 긴급 복원 시 Actions workflow와 Pages production 자동 배포를
먼저 중지하여 새 실행과 충돌하지 않게 한다. 웹은 Pages의 이전 성공 배포를 Rollback한다.
복원은 DB/학습 기록을 되돌리지 않는다. 배포는 직렬 실행하며 진행 중 작업을 자동 취소하지 않는다.

## 로컬 파일

`.env*` 비밀값·강의 원본 PDF·runs 생성물·work/tmp·가상환경은 Git에 넣지 않는다.
기존 `.gitignore`의 사람이 고른 `_pairs`/보류/핀 예외와 버전 관리 대상 시간표·작업 문서는 보존한다.
원본 강의/자료와 로컬 상태는 Git clone만으로 복제되지 않는다.

공식 근거: [Cloud Run source 배포 권한](https://docs.cloud.google.com/run/docs/deploying-source-code),
[Google GitHub OIDC](https://github.com/google-github-actions/auth),
[Pages Git SHA 변수](https://developers.cloudflare.com/pages/configuration/build-configuration/),
[Pages 빌드 제한](https://developers.cloudflare.com/pages/platform/limits/).
