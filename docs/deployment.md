# 배포

모든 변경은 [개발 루프](development/README.md)의 구현 승인·실제 검사·코드 리뷰·중요 배포 승인을 따른다.
서버 배포는 `./deploy.ps1 -ChangeId <작업ID>`로 실행한다. 해당 코드 해시의 승인/검사/리뷰가 없으면
클라우드 호출 전에 중단한다. 서버/웹 모두 [고정 후보·사후 검사 절차](development/release-and-incidents.md)를 따른다.
웹은 검증된 web/dist 후보를 승인된 publish-web 명령으로 배포한다. 기존 master push가 별도의 배포를
유발할 수 있으므로 이 절차를 우회하는 직접 push는 하지 않는다. 원격 브랜치/Pages 설정 자체는 이번에 변경하지 않았다.

서버 독립 환경은 server 폴더에서 requirements.txt를 설치한다. `../studyez_contracts`의 editable 설치가 포함된다.
기존 환경도 한 번 다시 설치해야 한다. 서버 패키지는 `prepare-build.ps1 -Destination <새폴더>`로 준비하며,
app·공용 계약·requirements·Dockerfile만 포함한다. 이 패키지를 release_evidence.py prepare로 검증·고정하고
후보에 대한 승인을 받은 뒤 deploy.ps1이 고정 패키지만 배포한다.
서버 배포는 attempt별 고유 revision을 트래픽 없이 생성한 뒤 준비 상태와 실제 생성 버전을 확인한다.
deploy-revision.ps1이 해당 버전으로 100% 트래픽을 명시 전환하고 생성·준비·트래픽 버전의 일치를 검증한다.
기존 버전의 정상 응답만으로 이번 배포를 성공 처리하지 않는다. 회귀 검사는 tests/development/test_server_deploy.py를 따른다.
`gcloud run deploy --source server`처럼 서버 폴더만 직접 보내면 공용 계약이 빠지므로 사용하지 않는다.
로컬 패키지 준비는 운영 배포가 아니다.

2026-10-19 학습 기록 보존은 API 배포 전에 `init-db`로 `bank_version`,
`bank_state_archive` 표를 만들고 RLS 활성화를 확인한다. 은행 교체·공용 문항 수정은
원본 은행과 사용자 상태를 같은 트랜잭션에서 보관한 후, 내용이 같은 문항의 기록만
이전한다. ID 재사용만으로 학습도를 이전하지 않는다. 관리자 이용현황은 보관된
버전별 최신 상태를 읽고 복구된 평가의 원본 식별자로 중복을 제거한다.
일회성 복구의 사용자 제외 범위와 결과는 `work/study-retention-20261019/`에 기록한다.

Supabase(로그인·DB) · R2(파일) · Cloud Run(API) + Cloudflare
Pages(정적 프론트).

```
Cloudflare Pages  ──►  Cloud Run (studyez-api)  ──►  Supabase Postgres
   web/ 빌드                  server/                      R2
```

## 한 번만 하는 것

2026-10-18 기본 예습 프롬프트 편집은 API 배포 전에 `init-db`로 `site_prompt` 표를 만든다.
표에는 RLS가 적용되며 읽기·쓰기는 관리자 전용 `GET|PUT /api/admin/preview-prompt`를 사용한다.
API를 먼저 배포한 다음 웹을 배포한다. 강의 패널의 예습 → 기본 프롬프트 수정에서 저장하며,
기본 링크를 새로 만들 때 최신 저장값을 읽는다. 빈 값은 기본 문구로 복원한다.
기존 예습 대화와 개인 프롬프트는 변경하지 않는다.

2026-10-16 전체 문제 열람은 DB 변경 없이 API를 먼저, 웹을 다음에 배포한다.
`GET …/bank/catalog`는 공개된 문제은행과 본인의 개인 문제를 PDF 슬라이드 순서로 제공한다.
정답·해설은 `GET …/bank/catalog/{question_id}?buildId=…`에서 필요할 때만 읽는다.
두 경로는 학습 상태·세션·열람 기록·복습 일정을 생성하거나 변경하지 않는다.
비활성화 문항도 목록에 포함하며 S1 위치가 없는 문항은 마지막에 표시한다.

2026-10-16 Quiz Bank 3문항 선로딩은 DB 변경 없이 API를 먼저, 웹을 다음에 배포한다.
`prepare-buffer`는 복사한 학습 상태에서 Good 기준 다음 3문항과 각 단계의 다른 평가 분기를 준비한다.
문제·선지·해설·주요 이미지를 함께 준비하며 미리 읽기만으로 노출·정답 공개·평가를 저장하지 않는다.
웹은 준비된 문항의 조작을 허용하고 선지 공개·정답 공개·채점을 입력 순서대로 백그라운드 저장한다.
평가 때마다 버퍼를 보충하며 저장 중인 평가도 읽기 전용으로 투영할 수 있다.
2026-10-17 웹 수정: 문제 전환·저장 응답 중에도 진행 중인 버퍼 보충을 유지한다.
응답 순서가 뒤바뀌면 창을 병합해 더 앞서 준비한 문항·평가 분기를 보존하며,
편집·학습 선택 변경·저장 실패 복구·화면 종료 때는 진행 중인 요청을 취소한다.
이 수정은 웹 배포만 필요하다. 유한한 선로딩 범위를 보충보다 빨리 소진하면 대기는 생길 수 있다.
서버 선택이 달라지면 후속 저장을 취소하고 서버 문항으로 맞춘다. 저장 실패 시 실패한 문항과 입력을 복원한다.
`rate.retrySafe`는 마지막 평가의 같은 토큰·등급 재요청만 재사용해 응답 유실에 따른 중복 평가를 방지한다.
구 API에서는 기존 준비·공개·평가 경로로 동작한다.

2026-10-16 개인 문제 추가와 필수 암기(Essential)는 API를 먼저, 웹을 다음에 배포한다.
기존 `bank_personal_edit`에 `original.personalAdded`로 개인 추가 문항을 구분하므로 새 DB 표·칼럼은 없다.
추가 문항은 공용 은행 재생성과 독립적으로 유지되며 계정별로 학습·모아 풀기·현황에 포함된다.
정책 3.11.0의 중요도는 Essential > Core > Important > Optional이고 Essential 목표는 .90이다.
출제 프롬프트 1.67과 CLI 검수는 명시적인 필수 암기·시험 출제 강조의 원본 근거를 요구한다.
배포만으로 기존 문항의 중요도를 일괄 변경하거나 문제은행을 다시 생성하지 않는다.

2026-10-16 시간표 첫 로딩 개선도 DB 변경 없이 API를 먼저, 웹을 다음에 배포한다.
홈은 가벼운 시간표만 계정 조회와 병렬로 받으며 다른 화면의 계정 조회는 시간표를 미리 읽지 않는다.
학습률은 사용자가 켰을 때 현재 주·월만 `include_cards=false`로 조회한다.
덱 목록은 모아받기를 펼칠 때 주간 날짜 범위 또는 `subject`로 좁혀 읽고,
강의 패널 코드는 강의를 누를 때 불러온다. 탭 복귀 조회는 1분 안에는 반복하지 않는다.

2026-10-16 학습 현황 지연 계산은 DB 변경 없이 API를 먼저, 웹을 다음에 배포한다.
학습 현황 화면은 `GET /api/timetable?include_study=false`로 목록만 읽고 집계는 접어 둔다.
펼칠 때만 선택한 블록을 `POST /api/timetable/study-progress`로 최대 8강의씩 계산한다.
접으면 다음 집계 요청을 중단하며, 기존 시간표 API의 기본 응답은 유지한다.

2026-10-16 학습현황의 개인 강의 숨김과 관리자 퀴즈 삭제는 API 배포 전에
`init-db`로 `study_hidden_lecture`, `quiz_bank_archive` 표를 만든다. 두 표에는 RLS를 적용한다.
API를 먼저 배포한 다음 웹을 배포한다. 숨김은 본인의 학습현황 목록·집계에만 적용하며
관리자 삭제는 현재 Quiz Bank 행을 원본 전체와 삭제자·시각을 기록한 보관 표로 옮긴다.
강의 자료·학습 상태·개인 수정·피드백은 삭제하지 않는다. 생성·검증 작업 중에는 삭제할 수 없다.

2026-10-16 관리자 목록 전송량 개선은 DB 스키마 변경 없이 API와 웹을 배포한다.
웹은 마지막 조회 이후 10분 간격으로 작업 현황만 읽으며, 작업 종료·실패·보류 시 결과 목록을 다시 읽는다.
숨겨진 탭에서는 갱신을 쉬고 돌아오면 10분이 지났을 때 작업 현황을 확인한다. 수동 새로고침도 가능하다.
로컬 러너는 관리자 화면과 독립적으로 계속 실행된다. API의 문제은행 요약은
행 `updated_at`과 현재 필기 파일명이 같으면 프로세스 내 캐시를 재사용한다.
원문과 검토 기록은 보존하며, 캐시가 없을 때도 요약에 필요한 JSON 항목만 조회한다.
API를 먼저 배포해 기존 웹의 반복 조회도 줄인 뒤 웹을 배포할 수 있다.

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

2026-10-15 모아풀기 생성 시각 표시는 API 배포 전에 `quiz_bank.linked_at`
nullable 시각 칼럼을 준비한다(`init-db`). 기존 링크 시각은 채우지 않는다.
새 공유 링크 저장·변경 시각을 기록하며 동일 링크 재전송은 시각을 바꾸지 않는다.
최종퀴즈 업로드 시각은 기존 `built_at`을 사용한다.

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

2026-10-12부터 V1 강의별 Main-Quiz 풀이와 기존 Study Engine 간격 계산을 사용한다.
문항 품질 검사·검토된 선지 풀을 유지하며 현재 Quiz Bank는 JSON 3.2를 생성한다. 중요도는
Core·Important·Optional, 독립 심화 표시는 advanced boolean이다. 기존 3.0·3.1 은행도 계속 읽는다.
V2의 learning_* 표와 학습 이력은 보존한다. 복귀를 위해 표·문제은행·개인 수정본을 삭제하지 않는다.
`/study`는 캘린더로 연결하고 기존 `/bank/<subject>/<runId>` 주소는 V1 풀이를 연다.


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
