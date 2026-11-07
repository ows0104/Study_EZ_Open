# 공동작업과 자동 배포

2026-11-05 사용자 요청으로 `master` 코드 변경의 자동 배포를 활성화한다. 이번 요청은
일반 코드 배포 자동화의 승인 근거이며, 새 기능의 구현 승인이나 운영 데이터 변경 승인을 대신하지 않는다.

## 작업 시작 대원칙 (예외 없음)

두 사람이 각자 여러 세션을 동시에 돌린다. 작업 범위가 겹치면 merge 충돌, 서로 덮어쓰기,
의도하지 않은 자동 배포로 이어진다. 그래서 사람이든 에이전트 세션이든 **새 기능·수정을 시작할 때마다**
아래 네 단계를 순서대로 마친 뒤에만 파일을 고친다. 하나라도 건너뛰었으면 작업을 시작하지 않은 것이다.

1. **기능 하나에 브랜치 하나를 새로 만든다.** 최신 master 위에서 만든다.
   기존 브랜치나 다른 기능의 브랜치를 재사용하지 않는다. master에서 직접 작업하지 않는다.
   ```bash
   git fetch origin
   git switch -c feat/<기능이름> origin/master
   git branch --unset-upstream   # 실수로 master에 push되는 것을 막는다
   ```
   한 사람이 세션을 여러 개 동시에 쓰면 세션마다 별도 worktree(별도 폴더)를 쓴다.
   같은 폴더에서 두 세션이 브랜치를 바꾸면 서로의 작업이 섞인다.
   ```bash
   git worktree add ../Study_EZ_<기능이름> -b feat/<기능이름> origin/master
   ```
2. **`git pull`로 대시보드를 최신으로 받는다.** 대시보드는 `dashboard` 브랜치의 `DASHBOARD.md`이며
   전용 폴더 `../Study_EZ_dashboard`에서 다룬다(최초 설정은 아래).
   ```bash
   git -C ../Study_EZ_dashboard pull
   ```
3. **대시보드에서 겹칠 여지를 확인한다.** "지금 하고 있는 작업"과 "앞으로 하기로 약속된 일"의
   영역·파일을 내 작업과 비교한다. 같은 파일, 같은 화면/API, 같은 DB 테이블, 같은 프롬프트를 건드릴
   가능성이 있으면 **시작하기 전에** 상대(또는 그 세션의 주인)와 조정한다. 범위를 나누거나, 순서를 정하거나,
   한쪽이 끝날 때까지 기다린다. 조정 결과는 양쪽 행의 메모에 적는다.
   에이전트 세션은 겹침을 발견하면 스스로 판단해 진행하지 않고 사람에게 묻는다.
4. **대시보드에 내 작업을 쓰고 push한 뒤 시작한다.** "지금 하고 있는 작업"에 우선순위·작업·작업자/세션·
   브랜치·건드리는 영역·파일·시작일을 적는다.
   ```bash
   git -C ../Study_EZ_dashboard add DASHBOARD.md
   git -C ../Study_EZ_dashboard commit -m "Claim: <작업>"
   git -C ../Study_EZ_dashboard push
   ```
   push가 거절되면 그사이 누가 대시보드를 고친 것이다. `git -C ../Study_EZ_dashboard pull --rebase`로 받은 뒤
   **3번부터 다시** 한다. 방금 들어온 작업이 내 작업과 겹칠 수 있다.

### 작업 중·종료 후

- 건드리는 파일이 처음 적은 범위를 넘어가면 대시보드 행을 고치고 3번 확인을 다시 한다.
- merge가 끝나거나 작업을 그만두면 즉시 "지금 하고 있는 작업"에서 지우고 "완료 기록"에 한 줄 남긴다.
  끝난 작업이 남아 있으면 다른 사람이 쓸데없이 기다린다.
- 아이디어는 "제안된 아이디어"에 적는다. 합의되어 "앞으로 하기로 약속된 일"로 옮기기 전에는 구현하지 않는다.

### 대시보드를 별도 브랜치에 두는 이유

- 기능 브랜치에 적으면 merge 전까지 상대에게 보이지 않아 대시보드가 의미 없다.
- master에 push하면 대시보드 한 줄 수정에도 운영 자동 배포(`deploy.yml`, Cloudflare Pages)가 실행된다.
- `dashboard` 브랜치는 master와 기록을 공유하지 않는 별도 브랜치다. 직접 push해도 배포가 실행되지 않는다.
  **`dashboard`를 master에 merge하거나 PR을 만들지 않는다.**

### 최초 1회 설정 (사람마다, PC마다)

```bash
git fetch origin
git worktree add ../Study_EZ_dashboard dashboard
sh .githooks/install.sh               # master 직접 push 차단 훅을 설치한다
```

`install.sh`는 `.githooks/pre-push`를 이 클론의 `.git/hooks/`로 복사한다.
커밋되는 설정이 아니므로 **클론마다 한 번** 돌려야 하고, 훅을 고친 뒤에도 다시
돌려야 한다. 설치됐는지 확인:

```bash
ls "$(git rev-parse --git-common-dir)/hooks/pre-push"
```

`core.hooksPath=.githooks`로 거는 길은 택하지 않았다. 그 경로는 작업본 안에서
풀리기 때문에, `.githooks`가 없는 옛 커밋에 올라간 worktree는 아무 경고도 없이
보호가 빠진다(2026-11-08 실측: 같은 push가 한 worktree에서는 거부되고 다른
worktree에서는 통과했다). `.git/hooks` 복사본은 공용 디렉터리에 있어서 체크아웃된
브랜치와 무관하게 모든 worktree에서 돈다.

### master 보호 (로컬 훅)

`.githooks/pre-push`가 두 가지를 거부한다.

- `refs/heads/master`로의 직접 push와 master 삭제. master는 PR 병합으로만 바뀐다.
- `dashboard` 외의 브랜치가 `DASHBOARD.md`를 담고 있는 경우.
  dashboard를 기능 브랜치에 merge해 master로 흘려보내는 길을 막는다.

**이것은 서버에서 강제되는 보호가 아니다.** 이 저장소는 비공개이고 계정이 무료
플랜이라 GitHub의 branch protection과 ruleset이 둘 다 403으로 막힌다(2026-11-08
확인). 그래서 같은 목적을 클라이언트에서 지킨다. 따라서

- `git push --no-verify`로 우회된다.
- `.githooks/install.sh`를 돌리지 않은 클론에서는 아예 돌지 않는다.
- GitHub 웹에서 하는 병합은 막지 못한다.

서버측으로 올리려면 GitHub Pro(유료)로 올리거나 저장소를 공개로 바꿔야 한다.
공개 전환은 학습 기록·배포 영수증·운영 경로가 함께 공개되므로 택하지 않았다.

## 작업 방법

1. 위 "작업 시작 대원칙" 네 단계를 마친다. 에이전트 브랜치 접두사는 `codex/`, `claude/`를 쓸 수 있다.
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
