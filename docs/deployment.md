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

### 3. `server/.env` 채우기

`<>`로 감싼 여섯 자리다. `deploy.ps1`이 안 채운 곳을 찾아 배포 전에 멈춘다.
`DATABASE_URL`은 **Transaction pooler(6543)**를 쓴다 — Cloud Run은 컨테이너가
수시로 뜨고 져서 연결을 오래 붙들지 않는다.

### 4. 스키마와 시간표

```bash
cd server
.venv/Scripts/python.exe -m app.cli init-db
.venv/Scripts/python.exe -m app.cli seed-timetable "…/2026_본1_2학기_시간표.json"
```

로컬에서 실 DB를 향해 돌린다. 학기 초에 한 번이다.

### 5. Cloud Run

```bash
cd server
./deploy.ps1
```

비밀값은 Secret Manager로 가고 배포 명령에는 들어가지 않는다. 끝나면 서비스
주소가 나온다.

### 6. Cloudflare Pages (GitHub 연동)

Workers & Pages → Create → Pages → **Connect to Git** → `ows0104/Study_EZ_Open`

| | |
|---|---|
| Production branch | `server` |
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
cd server && ./deploy.ps1
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
| `server/` 코드 | `cd server && ./deploy.ps1` |
| `web/` 코드 | `server` 브랜치에 push. Pages가 알아서 빌드한다 |
| 스키마 | `init-db`. 표를 지우지는 않으므로 컬럼을 뺄 때는 손으로 |
| 시간표 | `seed-timetable`. 없어진 칸은 지우고 매칭을 다시 계산한다 |

## 확인

```bash
curl https://studyez-api-xxxx.a.run.app/api/health
curl -i https://studyez-api-xxxx.a.run.app/api/timetable    # 401이어야 한다
```

로그인 없이 열리는 읽기 경로는 없다. `/api/health`만 예외다.
