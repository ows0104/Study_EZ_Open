# 배포 상태와 남은 일

2026-08-17 기준으로 **API·DB·프론트 배포와 인증 URL/CORS 연결까지 끝났다.**
실제 작업 순서와 복구 절차는
[Cloudflare Pages 배포 실행서](../cloudflare-pages-runbook.md)와
[R2 설정·키 교체 실행서](../r2-runbook.md)에 기록했다. 로컬 러너도 붙었다(§5).
남은 큰 일은 노출된 DB 비밀번호 교체다.

## 지금 상태

| | |
|---|---|
| Cloud Run | `studyez-api` · `asia-northeast3` · 리비전 `studyez-api-00003-krf` |
| API 주소 | `https://studyez-api-97999573571.asia-northeast3.run.app` |
| Supabase | 프로젝트 `dlvruugdigpbtgiwpdgs` · Seoul · 표 9개 · 시간표 369칸 |
| 로그인 | 이메일+비밀번호. JWKS(ES256)로 검증. Confirm email 켜짐 |
| R2 | 비공개 버킷 `runner` · 전용 `studyez-service` 토큰 · 연결 검증 완료 |
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

비공개 버킷 `runner`와 버킷 전용 Account API token `studyez-service`를 만들었다.
권한은 **Object Read & Write**, 대상은 `runner` 하나뿐이다. `meddeck-service`와
공유하지 않는다. 각 서비스가 자기 버킷과 토큰을 따로 가진다.

키는 `server/.env`와 Secret Manager의
`studyez-r2-access-key-id`·`studyez-r2-secret-access-key`에 반영했다. 실제 R2에
없는 객체를 HEAD해 인증 성공 뒤 404가 오는 것까지 확인했다. 생성·교체·노출 시
복구 방법은 [R2 설정·키 교체 실행서](../r2-runbook.md)를 그대로 따른다.

## 5. 로컬 러너 붙이기 — 완료

`runner/publish.py`가 산출물을 밀어 넣는다.

```bash
python -m runner publish 병리학 --dry-run    무엇이 올라갈지만 적는다
python -m runner publish 병리학
python -m runner publish 병리학 --notes-only  강의록만, 덱은 다음으로
```

무엇을 어디서 모으는지는 그 파일의 머리글에 있다. 요약하면 **한 강의의 자료가
두 군데서 온다** — 올해 필기와 Main-Quiz는 `runs/<올해 run_id>/`, 작년 필기와
Pre-Quiz·예습 대화는 `runs/<작년 run_id>/`다. Pre-Quiz를 작년 필기로 만들기
때문이고, 작년 짝은 `runner.matching`이 확정한 것만 쓴다.

**아직 필기가 없는 강의도 세운다**(`runner/ahead.py`). 계획이 올해 필기에서만
나오면 예습이 필요한 쪽 — 안 지나간 강의 — 이 통째로 빠진다. 병리학 2026에서
24칸이 그랬다. 그 자리는 시간표에서 찾아오고 붙는 것은 작년 강의록뿐이다.
`--no-ahead`로 끈다. 시간표는 `blocks.DEFAULT_SOURCE`(로컬 테스트 DB)를 보므로
학기 시간표를 갈면 `seed-timetable`을 다시 돌려야 한다.

점수기가 확신 못 한 짝은 붙이지 않고 후보와 함께 보고한다. 사람이 눈으로 확인한
것은 `runs/_pairs/<과목>.json`에 `{올해 run_id: 작년 run_id}`로 적어 두면 다음부터
그대로 쓴다. 병리학 24칸 실측은 확정 16 · 확인 필요 8이었고, 확인 필요 8은 전부
실습이거나 순번이 한쪽에만 있는 자리였다(시간표 `종양의 병리 실습(1)` ↔ 파일
`질병의 병리학적 이해 실습 7-종양의 병리 실습(1)`).

부르는 곳은 아래 아홉이고 전부 `Authorization: Bearer $RUNNER_TOKEN`이다. 토큰은
`server/.env`에 있고 Secret Manager의 `studyez-runner-token`에도 올라가 있다.

```
POST /api/admin/lectures                      강의 목록 upsert
POST /api/admin/lectures/{과목}/{run_id}/uploads          서명 URL 발급
POST /api/admin/lectures/{과목}/{run_id}/uploads/complete 확인
PUT  /api/admin/lectures/{과목}/{run_id}/run-meta/{main|pre}
PUT  /api/admin/lectures/{과목}/{run_id}/pre-items
PUT  /api/admin/lectures/{과목}/{run_id}/preview
GET  /api/admin/previews                      저장된 예습 링크 (서버 → 로컬)
POST /api/admin/prequiz-jobs/claim            일감 하나 집어 오기 + 박동
PUT  /api/admin/prequiz-jobs/{id}             진행 적기 + 박동 (몸이 비면 박동만)
```

**뒤의 셋은 방향이 반대다.** 사람이 `/admin`에서 저장하고 누르는 것을 로컬이
당겨 온다. 누르는 쪽(`POST …/prequiz-job`)은 관리자 세션이라 러너 토큰으로는
막혀 있다 — 비용이 나가는 일이라 사람이 눌러야 한다.

**일감에는 갈래가 있다**(`?kind=pre|main`, 기본 `pre`). 재료가 다르므로 만드는
명령이 다르다 — 예습은 예습 대화와 작년 필기로(`runner prequeue`), 복습은 올해
필기로(`runner watch --run-id`) 만든다. 러너가 `kind`를 보고 가른다. 한 갈래가
다른 갈래를 막지 않으므로 같은 편의 예습과 복습이 나란히 줄을 설 수 있다 — 다만
러너는 한 번에 하나씩 집어 간다.

파일은 서버를 거치지 않는다. Cloud Run의 요청 본문 상한(32MB)이 강의록 PDF보다
작아서, 서버는 키를 정하고 올라온 것을 확인만 한다.

**과목 이름을 이어 줄 필요는 아직 없었다.** 시간표는 "질병의 병리학적 이해"이고
폴더는 "병리학"이라 `course_alias`가 필요해 보이지만, 병리학은 한 교시에 강의가
하나뿐이라 날짜·교시만으로 칸이 정해진다(38/38 자동 연결). 한 교시에 여러 강의가
열리는 과목을 올릴 때 `/admin`에서 이어 주면 된다 — 러너 토큰으로는 못 하는
일이고 관리자 세션이 필요하다.

`ahead.py`도 그 표를 안 쓴다. 시간표에서 이 과목의 이름을 **이미 붙은 것에서
읽는다** — 올해 필기가 앉은 칸의 블럭 이름이 곧 그 과목이다. 그래서 올해 필기가
한 편도 없는 과목은 예습 자리를 못 세운다. 그건 막다른 길이 아니라 순서다:
한 편이 올라오면 나머지 칸이 다 따라 선다.

## 새로 배포할 때

`prequiz_job`·`runner_beat` 두 표는 2026-08-23에 생겼다. 마이그레이션 도구가
없으므로(`server/app/cli.py` 첫머리) 운영에 한 번 만들어야 한다.

```bash
cd server; .venv/Scripts/python.exe -m app.cli init-db   # 있는 표는 안 건드린다
./deploy.ps1
```

`create_all`은 **없는 표만 만든다.** 이미 서 있는 표에 칼럼이 느는 것은
`app.cli`의 `ADDED_COLUMNS`가 맡는다 — `init-db`가 지나며 붙인다. 칼럼의 **형이
바뀌거나 이름이 바뀌는 것**은 여전히 손으로 해야 한다.

### 2026-08-24에 붙은 칼럼 둘 — `prequiz_job.kind`·`prequiz_job.force`

`kind`는 복습 덱도 같은 우편함을 쓰게 되면서, `force`는 「다시 만들기」가 러너까지
가야 해서 붙었다. **배포보다 먼저 붙여야 한다** — 새 코드의 조회에 두 칼럼이 들어
있어서, 없으면 덱 일감 경로가 통째로 500을 낸다(버튼·캘린더 패널·`/admin` 배너).

```bash
cd server; .venv/Scripts/python.exe -m app.cli init-db   # 붙은 칼럼을 적어 준다
./deploy.ps1
```

로컬 테스트 DB(`server/local_test_data/studyez.db`)에는 아직 이 표가 없다 —
`blocks.py`가 시간표만 읽는 사본이라 그렇다. 넣을 필요가 없다.

### 2026-09-03에 붙은 칼럼 둘 — `prequiz_job.queue_rank`·`cancel_requested`

앞의 것은 사람이 줄에서 옮긴 자리, 뒤의 것은 「멈추기」다. **여기도 배포보다 먼저
붙여야 한다** — 일감을 집어 가는 조회(`claim`)가 두 칼럼을 다 읽으므로, 없으면
러너가 아무것도 못 집는다. 같은 명령 하나면 된다(`init-db`).

**러너도 같이 나가야 한다.** 멈추라는 말은 서버가 표에 적어 두고 러너가 받아
가는 것이라(`runner.agent`), 옛 러너가 도는 동안 누른 「멈추기」는 화면에만
남는다. 그때는 한 번 더 눌러 강제로 내릴 수 있지만, 노트북의 프로세스는 그대로
돈다 — 러너를 새로 띄우는 것이 먼저다.

칼럼이 0으로 서 있는 동안에도 순서는 이미 바뀐다. 그 값이 0인 줄은 **자동
순위**가 세우기 때문이다 — 내일 예습 → 오늘 복습 → 선 순서대로
(`routes/prequiz_jobs.queue_priority`, 관리자 지시 2026-09-03).

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
