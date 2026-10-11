# 배포

Supabase(로그인·DB) · R2(파일) · Cloud Run(API) + Cloudflare
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

이름은 `runner`. **공개로 열지 않는다** — 버킷이 비공개라는 것이 "로그인
필수"를 파일에도 성립시키는 유일한 수단이다.

API 토큰은 **Object Read & Write**, 대상은 `runner` 버킷만으로 좁힌다.
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

2026-10-10 복습 프롬프트 수정은 `profile.review_prompt` 칼럼을 먼저 준비한 뒤
API와 웹을 배포한다. `init-db`가 빈 문자열 기본값으로 추가하며 예습 프롬프트와
별도로 계정에 저장한다. 브리지 1.3.7은 기억된 동의 안내를 작은 박스로 표시한다.

2026-10-09 개인 문항 수정 기능은 `bank_personal_edit` 표를 먼저 준비한 뒤 API와 웹을 배포한다.
관리자에게 모든 수정을 전달하는 기능은 `bank_feedback.highlighted` 칼럼을 먼저 준비한다.
기존 명시적 제보는 강조 표시를 유지하고, 자동 전달되는 수정은 일반 피드백으로 표시한다.
개인 수정의 전후 비교를 개선 루프에 전달하려면 `bank_feedback.correction` JSON 칼럼을
API 배포 전에 추가한다. 기존 접수분은 본문에 남은 수정 제안으로 계속 검토할 수 있다.
`init-db`가 새 표를 만들고 RLS를 적용한다. 개인 수정은 본인 인증 API로만 읽고 쓰며,
공용 원문이 변경되면 이전 개인 수정본을 자동 적용하지 않는다.

피드백 기능 적용 시 `init-db`로 `site_feedback` 표를 만든 다음 API와 웹을 배포한다.
새 표에는 RLS가 자동 적용되어 Supabase 공개 API에서 직접 읽을 수 없다.
첨부는 비공개 R2의 `feedback/`에 저장하고 관리자 인증 API로만 제공한다.
피드백함은 최근 200건을 표시하며, 열어 둔 동안 15초마다 갱신한다.

```bash
cd server
.venv/Scripts/python.exe -m app.cli init-db
.venv/Scripts/python.exe -m app.cli seed-timetable
```

로컬에서 실 DB를 향해 돌린다. 학기 초에 한 번이다. 경로를 안 주면
[data/timetable/](../data/timetable)의 최신 학기 파일을 먹는다.

2026-10-06 개인 복습 링크 기능을 적용할 때도 `init-db`를 실행한다. 새 `user_review`
표를 만든 다음 API와 웹을 배포한다. 2026-10-09부터 직접 전송하는 복습 링크도
브리지 1.2.0에서 사용할 수 있다. 사이트가 구버전의 개인 대화 결과를 복습 저장
경로로 연결한다. 1.3.5 이상은 확장이 복습 결과를 직접 구분한다.
웹 빌드의 확장 ZIP은 manifest 버전으로 묶으며, 사이트 버튼·프롬프트 변경만으로
확장 업데이트를 요구하지 않는다.
이 표는 생성 시 행 보안(RLS)을 켠다. 이미 만든 표를 적용할 때에는
`ALTER TABLE public.user_review ENABLE ROW LEVEL SECURITY`를 실행한다.
복습 링크는 서버의 본인 확인 경로로만 제공한다.

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

학습요점 기반 학습(`/study`, `/api/learning`)을 처음 배포할 때는 **DB → API → 웹** 순서다.
서버 환경에서 `python -m app.cli init-db`를 먼저 실행하여 `learning_bank_version`,
`learning_legacy_state`, `learning_profile`, `learning_day`, `learning_session`,
`learning_attempt` 표를 만든다. 기존 은행·학습 상태를 삭제하거나 다시 생성하지 않는다.
테스트용 SQLite가 아닌 의도한 배포 DB인지 확인한 뒤 실행한다.

`STUDYEZ_LEARNING_ENABLED=0`은 새 학습 API를 끄는 복귀 스위치이며 기본값은 `1`이다.
기존 강의별 풀이는 `/bank/<subject>/<runId>?classic=1`로 접근한다.
기능을 꺼도 은행 버전 보존 코드는 동작하므로 위 표는 먼저 준비해야 한다.
기존 은행은 문항 단위의 보수적 범위로 읽고, v4 은행의 학습요점·범위 목록이 준비되면
그 목록을 사용한다. 과거 자기평가를 새 객관식 정답률로 바꾸지 않는다.

배포 후 공개된 강의의 `/study`에서 시작·재접속·해설 확인·되돌리기를 확인하고,
시험용 문항이 일반 풀이와 Anki 내보내기에 섞이지 않는지 점검한다.
실제 강의 3개(이해하기 쉬운 2개, 어려운 1개)에서 v2.0 생성 프롬프트로 새 은행을 만든 뒤
관리자 범위 검사로 자료 누락, 설명/최소 암기, 원본 근거, 변형·시험 문항을 검토한다.
생성된 범위 목록 자체가 원문을 빠짐없이 덮는지는 구조 검사만으로 보증되지 않는다.

| 무엇이 바뀌었나 | 할 일 |
|---|---|
| `server/` 코드 | `cd server; ./deploy.ps1` |
| `web/` 코드 | `master` 브랜치에 push. Pages가 알아서 빌드한다 |
| 스키마 | `init-db`. 표를 지우지는 않으므로 컬럼을 뺄 때는 손으로 |
| 시간표 | `seed-timetable`. 없어진 칸은 지우고 매칭을 다시 계산한다 |

## 같이 얹혀 있는 것 — 기생충학 땡시

`spotter/`가 **이 서버와 이 Supabase를 같이 쓴다.** 서버 코드는
`server/app/routes/spotter/`에 있고, R2 키는 `spotter/` 아래로 모인다.
학생이 두 앱에 각각 가입하지 않게 하려는 것이라 계정 표(`profile`)를 공유한다.

**앱별 권한 정책은 다르다.** 땡시는 `require_spotter`를 통해 자동 권한을 받고,
Study_EZ는 관리자 승인이 필요하다. 정책은 `server/app/models/accounts.py`에 있다.

배포할 때 이것 때문에 더 할 일:

| | |
|---|---|
| `CORS_ALLOWED_ORIGINS` | 땡시가 올라간 주소도 넣는다 (쉼표로 이어서) |
| Supabase **Redirect URLs** | 땡시 주소도 넣는다. 빠지면 비번 재설정 링크가 죽는다 |
| `init-db` | 필요한 땡시 표를 세운다. 모델 정본은 `server/app/models/spotter.py` |
| 문항 DB·사진 | `spotter/scripts/upload_web.py`가 서명 URL로 올린다 |

형제 앱을 어떻게 운영하는지, 세 번째를 어떻게 붙이는지는
[sibling-apps.md](sibling-apps.md)에 있다. 땡시 앱 자체의 문서는
[spotter/web/README.md](../spotter/web/README.md)다.

정적 배포본은 `python spotter/scripts/deploy_pages.py spotter-dist`로 만든다.
Cloudflare Pages가 연결된 배포 저장소에 `spotter-dist/` 내용을 반영하는 단계는 별도다.
원격 이력의 상태를 확인하고 배포하며, 과거 문서의 force-push 예시를 기본 절차로 쓰지 않는다.

## 확인

```bash
curl https://studyez-api-xxxx.a.run.app/api/health
curl -i https://studyez-api-xxxx.a.run.app/api/timetable    # 401이어야 한다
curl -i https://studyez-api-xxxx.a.run.app/api/spotter/db   # 401이어야 한다
```

로그인 없이 열리는 읽기 경로는 없다. `/api/health`만 예외다.
