# 형제 앱

계정은 하나, 문은 앱마다, 로그인은 한 번.

```
spotter.studyez.kr ─┐
studyez.kr         ─┼─►  studyez-api (Cloud Run)  ─►  Supabase Postgres
<세 번째>.studyez.kr ─┘        /api/<app>/*                 R2 (spotter/, lectures/)

           Supabase Auth — 세션은 Domain=.studyez.kr 쿠키
```

앱이 늘어도 늘지 않는 것 셋: Supabase 프로젝트, Cloud Run 서비스, 계정 표.

## 문은 어떻게 갈리나

`server/app/models.py`의 `APP_POLICY` 한 줄이 그 앱의 접근 정책이다.

| | 뜻 | 쓰는 앱 |
|---|---|---|
| `auto` | 로그인하면 그 자리에서 권한이 나온다 | 땡시 — 우리가 만든 문항과 사진 |
| `manual` | 사람이 `/admin`에서 준다 | Study_EZ — 남이 만든 강의 필기 |

권한은 `app_grant(user_id, app, role)`에 줄로 남는다. `auto`인 앱도 줄을 남기는
이유는, 나중에 누군가를 막아야 할 때 지울 것이 있어야 하기 때문이다.

`profile.is_admin`은 이 표와 **별개**다. 플랫폼 전체를 관리하는 사람이고 앱마다
갈라지지 않는다. `profile.is_approved`는 2026-09-06에 표로 옮겨 갔고 지금은
아무도 안 읽는다(칼럼만 남아 있다).

## 세 번째 앱을 붙이는 법

### 서버 — 네 곳

```python
# 1. models.py — 이름과 정책
APP_NEWTHING = "newthing"
APP_POLICY = {APP_STUDYEZ: POLICY_MANUAL, APP_SPOTTER: POLICY_AUTO,
              APP_NEWTHING: POLICY_AUTO}

# 2. routes/newthing.py — 그 앱의 문
require_newthing = require_app(APP_NEWTHING)

@router.get("/thing")
def read_thing(user: CurrentUser = Depends(require_newthing)): ...

# 3. main.py
app.include_router(newthing.router, prefix="/api")
```

4. 표가 필요하면 `models.py`에 `newthing_` 접두사로 세운다. DB를 함께 쓰므로
   이름이 겹치면 안 된다 — `quiz_attempt`가 이미 Study_EZ의 Pre-Quiz 것이다.

그리고 `python -m app.cli init-db`, `./deploy.ps1`.

### 프론트 — 세 곳

빌드 도구가 있으면(Vite) Study_EZ의 `web/src/supabase.ts`를, 없으면 땡시의
`web/auth.js`를 베낀다. 어느 쪽이든 **같은 세 가지**를 지켜야 로그인이 나눠진다.

| | 값 |
|---|---|
| 저장소 | `platform/session/session.js`의 `cookieStorage` |
| 도메인 | `studyez.kr` (`VITE_SESSION_DOMAIN` 또는 `CONFIG.sessionDomain`) |
| 키 | `SharedSession.storageKey(supabaseUrl)` — `sb-<ref>-auth-token` |

세션의 **모양**도 Supabase auth-js가 저장하는 것을 따라야 한다
(`{access_token, refresh_token, expires_at, user, …}`). 우리 형식을 쓰면 형제가
못 읽는다.

빌드 도구가 없는 앱은 `session.js`를 사본으로 들고 간다. 땡시의
`scripts/sync_shared.py`가 그 일을 하고 `--check`로 갈라졌는지 본다.

### 그 밖 — 세 곳

1. `server/.env`의 `CORS_ALLOWED_ORIGINS`에 새 오리진을 더하고 배포한다. 경로가 아니라
   오리진이다 — `https://spotter.studyez.kr` 까지만 적는다.
2. Supabase **Authentication → URL Configuration → Redirect URLs**에 새 주소를
   더한다. **빠뜨리면 비밀번호 재설정 메일은 오는데 링크가 죽는다.**
3. Cloudflare에 서브도메인을 붙인다(아래).

## 서브도메인 붙이기

DNS는 Cloudflare에 있다(`docs/domain-runbook.md`). 앱마다 Pages 프로젝트 하나다 —
같이 배포되지 않아야 하나가 깨져도 나머지가 산다.

1. **Cloudflare Pages → Create project → Connect to Git**에서 그 앱의 저장소를
   고른다. 땡시는 `ows0104/Spotter_Quiz`다.
2. 빌드 설정:

   | | 값 |
   |---|---|
   | Framework preset | None |
   | Build command | (비움) |
   | Build output directory | `/` (저장소 루트) |

   **저장소 루트를 통째로 낸다.** 이 저장소는 루트가 이미 과목 허브이고
   `exam1/`·`trunk/`·`head-neck/`·`neuro/`·`parasitology/`가 그 아래 있다.
   한 과목만 내려고 출력 디렉터리를 그 폴더로 좁히면 나머지가 사라진다.
3. 프로젝트 → **Custom domains → Set up a domain** → `spotter.studyez.kr`.
   Cloudflare가 CNAME을 알아서 넣는다(같은 계정의 존이므로).
4. `Active / SSL enabled`가 될 때까지 기다린다. 보통 1~2분이다.

   기생충학은 `https://spotter.studyez.kr/parasitology/`가 된다. 로그인이
   필요한 것은 그 하나뿐이고, 해부학 넷은 로그인 없이 그대로 돈다 — 한
   도메인 아래 있어도 문은 앱마다 따로다.

세션 공유는 **여기까지 끝나야 실제로 동작한다.** 그전에는 형제가 서로 다른 등록
도메인에 있어서 쿠키가 안 넘어간다 — 공유만 안 되고 로그인은 그대로 된다.

## 알아 둘 것 둘

**토큰 갱신이 겹칠 수 있다.** 두 앱을 동시에 열어 두면 한쪽이 갱신한 직후 다른
쪽이 옛 리프레시 토큰으로 갱신하려 들 수 있다. Supabase의 재사용 유예 창(기본
10초) 안이면 통과하고, 아니면 한쪽이 다시 로그인한다. 잦으면 Supabase의
**Refresh Token Reuse Interval**을 키운다.

**쿠키가 거부되면 조용히 떨어진다.** `Domain=.localhost`처럼 브라우저가 받아
주지 않는 자리에서는 쿠키가 예외 없이 그냥 사라진다. `session.js`는 쓴 뒤 되읽어
확인하고, 안 들어갔으면 localStorage로 떨어진다 — 공유는 잃지만 그 앱은 돈다.

## 앱 안의 갈래 — 과목

땡시(`spotter`)는 **과목 다섯이 한 앱**이다(`routes/spotter.py`의 `SUBJECTS`).
문은 `require_spotter` 하나이고, 로그인하면 다섯이 다 열린다. 갈리는 것은 R2
키(`spotter/<과목>/`)와 사이트 경로(`spotter.studyez.kr/<과목>/`)뿐이다.

**앱과 과목을 가르는 기준은 문이다.** 문이 다르면 앱이고(Study_EZ는 승인이
필요해서 앱이다), 같으면 과목이다. 해부학 넷과 기생충학은 같은 사람에게 같은
조건으로 열려야 해서 과목으로 뒀다 — 앱으로 갈랐으면 `app_grant`에 줄이 다섯
생기고 승인 화면에 체크박스가 다섯 늘었을 것이다.

과목을 더하는 것은 `SUBJECTS`에 한 줄, 그리고 자료를 올리는 것뿐이다.
땡시 앱 자체의 문서는 `Spotter_Quiz/web/README.md`에 있다.
