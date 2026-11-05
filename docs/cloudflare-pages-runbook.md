# Cloudflare Pages 배포 실행서

2026-11-05 자동 배포 구성은 [협업·자동 배포](development/collaboration.md)가 정본이다.
현재 build command는 `npm run build:pages`이며 preview 자동 배포는 끈다.
아래 최초 설치 기록의 `npm run build`는 복구 시 현재 명령으로 바꿔 적용한다.

이 문서는 Claude·Codex 같은 다음 작업자가 Study_EZ 프론트를 다시 배포하거나
설정을 복구할 때 그대로 따라 할 수 있는 실행 기록이다. 2026-08-17에 아래
절차로 실제 운영 배포를 완료했다.

## 현재 운영값

| 항목 | 값 |
|---|---|
| GitHub 저장소 | `ows0104/Study_EZ_Open` |
| 운영 브랜치 | `master` |
| Cloudflare Pages 프로젝트 | `study-ez-open` |
| 운영 프론트 | `https://study-ez-open.pages.dev` |
| 운영 API | `https://studyez-api-97999573571.asia-northeast3.run.app` |
| Supabase 프로젝트 | `dlvruugdigpbtgiwpdgs` |
| Cloud Run 리전 | `asia-northeast3` |

## 작업 전 확인

1. 저장소 루트에서 `git branch --show-current`가 `master`인지 확인한다.
2. 사용자 변경 파일은 건드리지 않는다.
3. `cd web; npm.cmd run build`가 성공하는지 확인한다. Windows PowerShell의
   실행 정책 때문에 `npm`이 막히면 `npm.cmd`를 쓴다.
4. `web/.env.production`에 아래 세 키가 모두 있는지만 확인한다. 값을 로그나
   대화에 출력하지 않는다.

```
VITE_SUPABASE_URL
VITE_SUPABASE_ANON_KEY
VITE_API_BASE_URL
```

`VITE_SUPABASE_ANON_KEY`는 브라우저용 publishable 값이지만, 그래도 작업 로그에
불필요하게 반복하지 않는다. DB 비밀번호·runner token·R2 secret은 Pages에
절대로 넣지 않는다.

## GitHub 앱 연결

Cloudflare → Workers & Pages → Create application에서 GitHub 연결을 선택한다.

Cloudflare의 최신 화면은 처음에 **Create a Worker**라고 표시될 수 있다. 이때
Worker를 만들지 말고 화면의 **Looking to deploy Pages? → Get started**를 눌러
Pages 흐름으로 이동한다. 직접 경로는 다음 모양이다.

```
https://dash.cloudflare.com/<account-id>/pages/new/provider/github
```

GitHub에서 `Cloudflare Workers and Pages` 앱 설치 화면이 나오면:

1. 개인 계정 `ows0104`를 선택한다.
2. 기본값인 **All repositories**를 그대로 두지 않는다.
3. **Only select repositories**를 선택한다.
4. `Study_EZ_Open`만 고른 뒤 **Install & Authorize**한다.

이 설치는 저장소에 대한 지속적인 read/write 권한을 부여하므로, 자동화 작업자는
마지막 `Install & Authorize` 전에 사용자 확인을 받아야 한다.

## Pages 프로젝트 만들기

저장소 목록에서 `Study_EZ_Open`을 선택하고 **Begin setup**을 누른다.

| 설정 | 값 |
|---|---|
| Project name | `study-ez-open` |
| Production branch | `master` |
| Framework preset | `None` |
| Build command | `npm run build` |
| Build output directory | `dist` |
| Root directory (advanced) | `web` |

`Root directory (advanced)`를 먼저 펼쳐야 `web`을 입력할 수 있다. 이 값이
비어 있으면 저장소 루트에서 `package.json`을 찾다가 즉시 실패한다.

`Environment variables (advanced)`를 펼치고 아래 세 항목을 Production/Preview
빌드 변수로 추가한다. 값은 `web/.env.production`에서 읽어 입력한다.

```
VITE_SUPABASE_URL
VITE_SUPABASE_ANON_KEY
VITE_API_BASE_URL
```

입력값을 다시 확인한 뒤 **Save and Deploy**를 누른다. 공개 웹사이트를 만드는
외부 변경이므로 자동화 작업자는 이 마지막 버튼 직전에 사용자 확인을 받는다.

성공 기준:

- 화면에 `Success! Your project is deployed`가 보인다.
- `https://study-ez-open.pages.dev`를 열면 `Study_EZ` 로그인 화면이 나온다.
- 배포 로그에서 `npm run build`와 Vite 빌드가 성공한다.

## Supabase 인증 URL 연결

Supabase → 프로젝트 `dlvruugdigpbtgiwpdgs` → Authentication → URL Configuration.

```
Site URL
https://study-ez-open.pages.dev

Redirect URLs
https://study-ez-open.pages.dev/**
http://localhost:5173/**
```

Site URL은 **Save changes**, Redirect URLs는 **Save URLs**로 각각 저장한다.
저장 후 페이지를 새로고침해 Site URL과 두 redirect URL이 남아 있는지 확인한다.

## API CORS 연결과 재배포

`server/.env`에서 이 한 줄만 바꾼다. 다른 비밀값은 출력하거나 수정하지 않는다.

```
CORS_ALLOWED_ORIGINS=https://study-ez-open.pages.dev,https://studyez.kr
```

커스텀 도메인 `studyez.kr`를 붙이면서 origin이 둘이 됐다. 쉼표로 나열하면 되고
`deploy.ps1`이 `^|^` 구분자로 넘기므로 값이 쉼표에서 잘리지 않는다. 도메인 연결
전체 순서는 [domain-runbook.md](domain-runbook.md)에 있다.

그 뒤 PowerShell에서:

```powershell
cd server
./deploy.ps1
```

스크립트는 Secret Manager를 동기화하고 Cloud Run을 새 리비전으로 배포한다.
2026-08-17 최신 배포 결과는 `studyez-api-00003-krf`, 트래픽 100%였다.
R2 설정까지 포함한 최신 서버 배포이며, R2 작업은
[r2-runbook.md](r2-runbook.md)에 따로 기록했다.

## 검증

프론트:

```text
https://study-ez-open.pages.dev
```

API 상태와 CORS:

```powershell
curl.exe -i -H "Origin: https://study-ez-open.pages.dev" `
  "https://studyez-api-97999573571.asia-northeast3.run.app/api/health"
```

성공 기준:

```text
HTTP/1.1 200 OK
access-control-allow-origin: https://study-ez-open.pages.dev
```

로그인하지 않은 보호 경로는 계속 `401`이어야 한다.

## 자주 막히는 지점

- Cloudflare 첫 화면이 Worker 생성처럼 보여도 Pages용 `Get started` 링크를 쓴다.
- GitHub 앱 권한은 모든 저장소가 아니라 `Study_EZ_Open` 하나로 제한한다.
- 저장소 목록이 잠시 비어 보이면 몇 초 기다린다. GitHub 연결 동기화가 늦을 수 있다.
- Cloudflare 폼의 advanced 섹션은 펼치기 전에는 내부 input이 숨겨져 있다.
- `Root directory=web`을 빠뜨리지 않는다.
- 브랜치는 예전 문서의 `server`가 아니라 현재 운영 브랜치 `master`다.
- Pages 배포 성공만으로 로그인 연동이 끝난 것이 아니다. Supabase URL과 API CORS를
  모두 같은 Pages origin으로 맞춰야 한다.
- 배포 탭을 닫으면 제출 전 폼 값이 사라진다. 마지막 확인 후에는 같은 탭에서 바로
  `Save and Deploy`를 실행한다.
