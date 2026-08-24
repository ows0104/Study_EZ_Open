# 배포 상태와 남은 일

2026-08-17 기준으로 **API·DB·프론트 배포와 인증 URL/CORS 연결까지 끝났다.**
실제 작업 순서와 복구 절차는
[Cloudflare Pages 배포 실행서](cloudflare-pages-runbook.md)와
[R2 설정·키 교체 실행서](r2-runbook.md)에 기록했다. 남은 큰 일은 로컬 러너
연결과 노출된 DB 비밀번호 교체다.

## 지금 상태

| | |
|---|---|
| Cloud Run | `studyez-api` · `asia-northeast3` · 리비전 `studyez-api-00003-krf` |
| API 주소 | `https://studyez-api-97999573571.asia-northeast3.run.app` |
| Supabase | 프로젝트 `dlvruugdigpbtgiwpdgs` · Seoul · 표 9개 · 시간표 369칸 |
| 로그인 | 이메일+비밀번호. JWKS(ES256)로 검증. Confirm email 켜짐 |
| R2 | 비공개 버킷 `studyez` · 전용 `studyez-service` 토큰 · 연결 검증 완료 |
| 프론트 | `https://study-ez-open.pages.dev` · 배포 및 로그인 화면 확인 완료 |

확인된 것:

```
GET /api/health              → {"status":"ok","environment":"production"}
GET /api/timetable           → 401 (로그인 없이)
GET /api/timetable + 가짜토큰 → 401
GET https://study-ez-open.pages.dev → Study_EZ 로그인 화면
GET /api/health + Pages Origin → 200 + 정확한 CORS 허용 헤더
R2 없는 객체 HEAD              → 인증 성공 뒤 404 (`R2_AUTH_OK`)
```

## 1. Cloudflare Pages 올리기 — 완료

프로젝트 `study-ez-open`, 운영 브랜치 `master`로 배포했다.

저장소는 `ows0104/Study_EZ_Open`, 브랜치는 **`master`**.

`server` 브랜치는 PR #7로 master에 병합되었고 그 뒤로 뒤처져 있다. `server/`와
`web/`는 master에 다 들어 있으므로 Pages는 master를 보면 된다.

Workers & Pages → Create → Pages → **Connect to Git**

| 설정 | 값 |
|---|---|
| Production branch | `master` |
| Framework preset | None |
| Build command | `npm run build` |
| Build output directory | `dist` |
| **Root directory** | **`web`** |

**Root directory를 `web`으로 잡지 않으면 빌드가 즉시 실패한다.** 저장소 뿌리에
`package.json`이 없다.

환경 변수 셋(Settings → Environment variables). `web/.env.production`에 같은
값이 이미 들어 있지만 그 파일은 커밋되지 않으므로 대시보드에 넣어야 한다.

```
VITE_SUPABASE_URL        https://dlvruugdigpbtgiwpdgs.supabase.co
VITE_SUPABASE_ANON_KEY   sb_publishable_cOcv3JFn7wtgjpSFjV89jA_OhhtTfJk
VITE_API_BASE_URL        https://studyez-api-97999573571.asia-northeast3.run.app
```

publishable 키는 브라우저 번들에 실리는 공개값이다. 실제 권한은 서버의 JWT
검증과 승인 게이트가 정한다.

## 2. 주소 두 곳 이어 주기 — 완료

Supabase Site URL·redirect URL과 서버 CORS를
`https://study-ez-open.pages.dev`로 연결했다.

Pages 주소가 나온 뒤에 해야 로그인이 된다.

**Supabase** → Authentication → URL Configuration

```
Site URL       https://<pages 주소>
Redirect URLs  https://<pages 주소>/**
               http://localhost:5173/**
```

안 하면 비밀번호 재설정 링크가 죽는다.

**서버 CORS** — `server/.env`의 `CORS_ALLOWED_ORIGINS`를 Pages 주소로 바꾸고

```bash
cd server; ./deploy.ps1
```

현재 `https://study-ez-open.pages.dev`로 설정해 Cloud Run 리비전
`studyez-api-00003-krf`에 배포했고, 응답 헤더까지 확인했다.

## 3. 첫 로그인과 승인

`STUDYEZ_ADMIN_EMAILS`에 `developer@studyez.kr`, `ows0104@gmail.com`이 들어 있다.
이 주소로 가입하면 **관리자이자 자동 승인**이다.

2026-08-17 운영 DB 확인 결과:

- `ows0104@gmail.com` — 관리자, 승인 완료
- `ows0104@snu.ac.kr` — 일반 사용자, 승인 완료

따라서 현재 사용할 관리자 계정은 `ows0104@gmail.com`이다. 비밀번호는 문서나
대화에 남기지 않고 계정 소유자만 관리한다.

1. Pages 주소에서 가입 → 확인 메일의 링크를 누른다
2. 로그인하면 캘린더가 보여야 한다 (369칸, 강의 자료는 아직 없으니 점은 없다)
3. 상단 `관리`에서 계정 표를 확인한다

다른 사람은 가입해도 "승인 대기 중"만 보인다. `/admin`의 계정 표에서 승인해야
자료가 열린다. 관리자가 자기 승인을 내리는 것은 막혀 있다.

**가입이 몰리면 확인 메일이 밀린다.** Supabase 기본 발송은 시간당 몇 통이
한계다. 학년 전체를 한꺼번에 받을 생각이면 Authentication → Emails → SMTP
Settings에 외부 발송(Resend 등)을 붙여야 한다.

## 4. R2 켜기 — 완료

비공개 버킷 `studyez`와 버킷 전용 Account API token `studyez-service`를 만들었다.
권한은 **Object Read & Write**, 대상은 `studyez` 하나뿐이다. `meddeck-service`와
공유하지 않는다. 각 서비스가 자기 버킷과 토큰을 따로 가진다.

키는 `server/.env`와 Secret Manager의
`studyez-r2-access-key-id`·`studyez-r2-secret-access-key`에 반영했다. 실제 R2에
없는 객체를 HEAD해 인증 성공 뒤 404가 오는 것까지 확인했다. 생성·교체·노출 시
복구 방법은 [R2 설정·키 교체 실행서](r2-runbook.md)를 그대로 따른다.

## 5. 로컬 러너 붙이기

파이프라인이 산출물을 밀어 넣는 부분은 아직 안 짜여 있다. 계약과 엔드포인트는
[server/README.md](../server/README.md)에 있다.

```
POST /api/admin/lectures                      강의 목록 upsert
POST /api/admin/lectures/{과목}/{run_id}/uploads          서명 URL 발급
POST /api/admin/lectures/{과목}/{run_id}/uploads/complete 확인
PUT  /api/admin/lectures/{과목}/{run_id}/run-meta/{main|pre}
PUT  /api/admin/lectures/{과목}/{run_id}/pre-items
PUT  /api/admin/lectures/{과목}/{run_id}/preview
PUT  /api/admin/prequiz-jobs/{id}             진행 적기 + 박동 (몸이 비면 박동만)
```

전부 `Authorization: Bearer $RUNNER_TOKEN`. 토큰은 `server/.env`에 있고 Secret
Manager의 `studyez-runner-token`에도 올라가 있다.

파일은 서버를 거치지 않는다. Cloud Run의 요청 본문 상한(32MB)이 강의록 PDF보다
작아서, 서버는 키를 정하고 올라온 것을 확인만 한다.

## 손대야 할 것 두 가지

**DB 비밀번호를 바꾸는 게 좋다.** 대화 기록에 평문으로 남았다. Supabase →
Settings → Database → Reset database password. 바꾼 뒤:

```bash
cd server; ./setup-env.ps1   # DATABASE_URL만 다시 넣는다
./deploy.ps1
```

특수문자를 쓰면 연결 문자열에서 퍼센트 인코딩해야 한다 — `@`는 사용자 정보와
호스트를 가르는 문자고 `#`은 fragment 시작이라 그냥 넣으면 주소가 잘린다.
영문+숫자만 쓰면 신경 쓸 일이 없다.

**`/c/` 대화 링크는 아직 관리자에게만 간다.** 안정되면 `server/.env`의
`STUDYEZ_SHOW_CONVERSATION_URL=true`로 바꾸고 재배포하면 모두에게 열린다.
