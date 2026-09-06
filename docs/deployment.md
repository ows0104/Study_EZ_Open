# 배포

운영 지점 셋. Supabase(로그인·DB) · R2(파일) · Cloud Run(API) + Cloudflare
Pages(정적 프론트).

```
Cloudflare Pages  ──►  Cloud Run (studyez-api)  ──►  Supabase Postgres
   web/ 빌드                  server/                      R2
```

## 한 번만 하는 것

### 1. Supabase 프로젝트

리전은 **Northeast Asia (Seoul)**. Cloud Run이 서울에 있어 왕복이 짧아진다.
DB 비밀번호는 만들 때만 보여 주므로 그 자리에서 복사한다.

**Authentication → Sign In / Providers → Email**

| | |
|---|---|
| Enable Email provider | 켠다 |
| Confirm email | 켠다 |
| Secure email change | 켠다 |

**매직링크(OTP)는 쓰지 않는다.** 로그인할 때마다 메일이 한 통씩 나가는데
Supabase 기본 발송은 시간당 몇 통이 한계라 한 학년이 쓰면 첫날에 막힌다.
비밀번호 방식은 가입 확인과 재설정 때만 메일을 쓴다.

그래도 가입이 몰리면 확인 메일이 밀린다. 학년 전체를 한꺼번에 받을 생각이면
**Authentication → Emails → SMTP Settings**에 외부 발송(Resend 등)을 붙이는
편이 안전하다.

**Authentication → URL Configuration**

```
Site URL       https://<pages 주소>
Redirect URLs  https://<pages 주소>/**
               http://localhost:5173/**
```

비밀번호 재설정 링크가 여기로 돌아온다. 등록하지 않으면 링크가 죽는다.

### 2. R2 버킷

이름은 `studyez`. **공개로 열지 않는다** — 버킷이 비공개라는 것이 "로그인
필수"를 파일에도 성립시키는 유일한 수단이다.

API 토큰은 **Object Read & Write**, 대상은 `studyez` 버킷만으로 좁힌다.
실제 대시보드 순서, 비밀키를 로그에 남기지 않는 방법, 키 노출 시 교체 절차는
[r2-runbook.md](r2-runbook.md)에 있다.

### 3. 값 채우기

```bash
cd server
./setup-env.ps1
```

물어보는 대로 붙여넣으면 `server/.env`와 `web/.env.production`을 함께 쓴다.
어디서 가져오는 값인지 매번 알려 주고, 형식이 어긋나면 그 자리에서 되묻는다.
비밀값은 입력할 때 화면에 찍히지 않는다. 이미 채운 값은 건너뛰므로 한 곳만
고칠 때 다시 돌려도 된다.

채울 것은 **다섯 개**다.

| | 어디서 |
|---|---|
| `SUPABASE_URL` | Project Settings → Data API → Project URL |
| `DATABASE_URL` | Project Settings → Database → Connection string → URI |
| `R2_ENDPOINT_URL` | R2 → 버킷 → Settings → S3 API (끝의 `/버킷이름`은 뗀다) |
| `R2_ACCESS_KEY_ID` | R2 → API → Manage API tokens |
| `R2_SECRET_ACCESS_KEY` | 같은 화면. 한 번만 보인다 |

`SUPABASE_JWT_SECRET`은 **비워 둔다.** 비우면 Supabase의 공개 키(JWKS)로
RS256 검증을 하고, 요즘 Supabase는 비대칭 키가 기본이라 그 편이 정석이다.
비밀값을 하나 덜 다루게 되는 것은 덤이다.

`DATABASE_URL`은 **Transaction pooler(6543)**를 쓴다 — Cloud Run은 컨테이너가
수시로 뜨고 져서 연결을 오래 붙들지 않는다. `[YOUR-PASSWORD]` 자리를 안 바꾸면
스크립트가 잡아 준다.

손으로 고치고 싶으면 `.env`를 직접 열어도 된다. `deploy.ps1`이 안 채운 곳을
찾아 배포 전에 멈춘다.

자동화 작업자가 브라우저에서 R2 키를 복사하는 경우에는 일반 PowerShell
프롬프트에 붙여넣지 않는다. 다음 보조 스크립트가 클립보드 값을 화면에 출력하지
않고 한 필드만 저장한 뒤 클립보드를 지운다.

```powershell
./set-r2-key-from-clipboard.ps1 -Field AccessKeyId
./set-r2-key-from-clipboard.ps1 -Field SecretAccessKey
```

### 4. 스키마와 시간표

```bash
cd server
.venv/Scripts/python.exe -m app.cli init-db
.venv/Scripts/python.exe -m app.cli seed-timetable
```

로컬에서 실 DB를 향해 돌린다. 학기 초에 한 번이다. 경로를 안 주면
[data/timetable/](../data/timetable/)의 최신 학기 파일을 먹는다.

**그 JSON을 만드는 코드는 이 저장소에 없다.** 학사 요람의 주별 시간표(이미지 PDF)를
사람이 옮겨 적은 것이다. 손으로 나온 것이라 **칸마다 `details`의 어디까지가 제목이고
어디부터가 담당인지가 흔들린다.**

    details    "(MDL)⏎연충란⏎최민호, 신은희, 여선주,⏎송현범, 김주현"
    professor  "연충란 최민호, 신은희, 여선주, 송현범, 김주현"   ← 소제목이 넘어왔다

2026 시간표 369칸 중 14칸이 그랬다. 화면은 담당에 든 줄을 제목에서 빼므로(교수 이름이
제목에 붙는 것을 막는 정상 동작이다) **그 칸은 제목이 통째로 사라진다.** 2026-08-31에
그 14칸을 JSON에서 고쳤고, `seed-timetable`도 넣기 전에 같은 것을 되돌린다
(`naming.strip_lead_topic`). 지금은 둘이 맞아서 「소제목을 뗀 칸」 줄이 안 뜬다 —
**다음 학기 JSON에서 그 줄이 뜨면 만드는 쪽에서 또 흔들린 것이다.**

원본은 요람의 「제 N 주」 표다(2026-08-31 확인: 8/31 실습 칸이 `감염의 기초 실습` /
`(MDL)` / `연충란` / 이름 다섯). 어느 쪽이 참인지 헷갈리면 `details`가 칸의 원문이고
`professor`가 거기서 뽑아낸 것이라고 보면 된다.

### 5. Cloud Run

```bash
cd server
./deploy.ps1
```

비밀값은 Secret Manager로 가고 배포 명령에는 들어가지 않는다. 끝나면 서비스
주소가 나온다.

### 6. Cloudflare Pages (GitHub 연동)

실제 화면을 따라 하는 상세 실행서는
[cloudflare-pages-runbook.md](cloudflare-pages-runbook.md)에 있다.

Workers & Pages → Create → Pages → **Connect to Git** → `ows0104/Study_EZ_Open`

| | |
|---|---|
| Production branch | `master` |
| Framework preset | None |
| Build command | `npm run build` |
| Build output directory | `dist` |
| Root directory | `web` |

**Root directory를 `web`으로 잡는 것이 핵심이다.** 저장소 뿌리에는
`package.json`이 없다.

환경 변수(Settings → Environment variables)에 셋을 넣는다. `.env.production`은
커밋되지 않으므로 여기 값이 빌드에 쓰인다.

```
VITE_SUPABASE_URL        https://xxxxxxxx.supabase.co
VITE_SUPABASE_ANON_KEY   <anon 키>
VITE_API_BASE_URL        https://studyez-api-xxxx.a.run.app
```

anon 키는 브라우저 번들에 들어가는 공개 값이다. 실제 권한은 서버의 JWT
검증과 승인 게이트가 정한다.

### 7. 서로를 가리키게 하기

Pages 주소가 나온 뒤 두 곳을 고친다.

```bash
# server/.env 의 CORS_ALLOWED_ORIGINS 를 Pages 주소로 바꾸고
cd server; ./deploy.ps1
```

그리고 Supabase의 Site URL·Redirect URLs에 같은 주소를 넣는다.

## 첫 로그인

`STUDYEZ_ADMIN_EMAILS`에 적힌 주소로 가입하면 **관리자이자 자동 승인**이다.
다른 사람은 가입해도 "승인 대기 중"만 보이고, `/admin`의 계정 표에서 승인해야
자료가 열린다.

관리자가 자기 승인을 내리는 것은 막혀 있다 — 되돌릴 사람이 자기뿐일 수 있다.

## 다시 배포할 때

| 무엇이 바뀌었나 | 할 일 |
|---|---|
| `server/` 코드 | `cd server; ./deploy.ps1` |
| `web/` 코드 | `master` 브랜치에 push. Pages가 알아서 빌드한다 |
| 스키마 | `init-db`. 표를 지우지는 않으므로 컬럼을 뺄 때는 손으로 |
| 시간표 | `seed-timetable`. 없어진 칸은 지우고 매칭을 다시 계산한다 |

## 같이 얹혀 있는 것 — 기생충학 땡시

`Spotter_Quiz`가 **이 서버와 이 Supabase를 같이 쓴다.** 코드는
`server/app/routes/spotter.py` 하나이고, R2 키는 `spotter/` 아래로 모인다.
학생이 두 앱에 각각 가입하지 않게 하려는 것이라 계정 표(`profile`)를 공유한다.

**문은 다르다.** 땡시 경로는 `require_approved_user`를 안 지나고
`get_current_user`만 지난다 — 가입하면 열린다. 승인 게이트는 강의 필기가
남이 만든 것이기 때문에 있는 것이고, 땡시 문항은 우리가 만들었다.

배포할 때 이것 때문에 더 할 일:

| | |
|---|---|
| `CORS_ALLOWED_ORIGINS` | 땡시가 올라간 주소도 넣는다 (쉼표로 이어서) |
| Supabase **Redirect URLs** | 땡시 주소도 넣는다. 빠지면 비번 재설정 링크가 죽는다 |
| `init-db` | `spotter_record`·`spotter_wrong`·`spotter_report` 셋을 세운다 |
| 문항 DB·사진 | `Spotter_Quiz/scripts/upload_web.py`가 서명 URL로 올린다 |

땡시 쪽 문서는 `Spotter_Quiz/web/README.md`에 있다.

## 확인

```bash
curl https://studyez-api-xxxx.a.run.app/api/health
curl -i https://studyez-api-xxxx.a.run.app/api/timetable    # 401이어야 한다
curl -i https://studyez-api-xxxx.a.run.app/api/spotter/db   # 401이어야 한다
```

로그인 없이 열리는 읽기 경로는 없다. `/api/health`만 예외다.
