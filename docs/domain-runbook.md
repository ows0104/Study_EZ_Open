# studyez.kr 연결 실행서

Cloudflare Pages(`study-ez-open.pages.dev`)에 커스텀 도메인 `studyez.kr`를 붙인다.
DNS는 hosting.kr에서 **Cloudflare 네임서버로 옮긴다** — apex(`studyez.kr`)를 Pages에
붙이려면 루트에 CNAME이 필요한데 hosting.kr DNS는 그걸 못 하고, Cloudflare는
CNAME flattening으로 한다.

**2026-08-18 연결 완료.** Cloudflare Pages의 커스텀 도메인은 `Active / SSL enabled`,
Supabase Site URL은 `https://studyez.kr`로 전환됐다. 기존 `pages.dev` redirect URL은
비상 접근 경로로 유지했다.

## 이 순서를 뒤집으면 메일이 끊긴다

**`studyez.kr`에는 Zoho Mail이 이미 붙어 있다.** 관리자 주소 `developer@studyez.kr`가
이것으로 돈다. 네임서버를 옮기면 hosting.kr의 존이 통째로 무효가 되므로, 아래
다섯 개가 **Cloudflare에 들어간 것을 눈으로 확인한 뒤에** 네임서버를 바꾼다.

| 종류 | 이름 | 값 |
|---|---|---|
| MX (우선순위 10) | `studyez.kr` | `mx.zoho.com` |
| MX (우선순위 20) | `studyez.kr` | `mx2.zoho.com` |
| MX (우선순위 50) | `studyez.kr` | `mx3.zoho.com` |
| TXT | `studyez.kr` | `v=spf1 include:zohomail.com ~all` |
| TXT | `studyez.kr` | `zoho-verification=zb98399849.zmverify.zoho.com` |
| TXT | `zmail._domainkey` | `v=DKIM1; k=rsa; p=MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQCBW3LXk+Is3Qo7ylU8m7lbnPYKWZLR1OCbUEDXVS1nP5k3IoV66k6HOm0JCpFMhfPsB8bwnlu1mT4CtPIK3IFfKCgX7yzj4TlQ9xrk9Dph3amzktuVjBpnl/c4z8cHroO6/K0AZAg9BEp+PjdmA837BNkVhM6bVCyV9KvWxT2PWQIDAQAB` |

Cloudflare는 존을 추가할 때 기존 레코드를 스캔해 자동으로 가져오지만, **DKIM은
셀렉터 이름을 알아야 찾을 수 있어서 놓치는 경우가 있다.** 위 표의 마지막 줄이
그것이다. 스캔 결과에 없으면 손으로 넣는다.

MX와 TXT는 **회색 구름(DNS only)**이어야 한다. 프록시(주황)를 켜면 메일이 죽는다.
Cloudflare가 알아서 회색으로 넣지만 확인한다.

## 이전 전 스냅샷 (2026-08-18, 8.8.8.8 조회)

```
NS     studyez.kr        ns1~ns4.hosting.co.kr
A      studyez.kr        75.2.85.42, 99.83.196.71   ← hosting.kr 주차 페이지. 버린다
CNAME  www.studyez.kr    studyez.kr                 ← 버린다 (아래에서 다시 만든다)
MX/TXT                   위 표
없는 것: AAAA, CAA, _dmarc, SRV
```

`studyez.kr`는 지금 HTTP로 hosting.kr 주차 페이지를 주고 HTTPS는 응답하지 않는다.
웹 쪽에는 살릴 것이 없다.

---

## 1. Cloudflare에 존 추가 — 완료

Cloudflare 대시보드 → **Add a domain** → `studyez.kr` → **Free** 플랜.

Cloudflare가 기존 레코드를 스캔한다. 끝나면 DNS 레코드 목록이 나온다.

## 2. 메일 레코드 대조 — 완료

위 표의 **여섯 줄(MX 3 + TXT 3)이 전부 있는지** 본다. 특히 `zmail._domainkey`.

없으면 **Add record**로 넣는다. DKIM TXT는 값이 길어서 붙여넣을 때 잘리기 쉬우니
넣은 뒤 다시 열어 `...PWQIDAQAB`로 끝나는지 확인한다.

## 3. 주차 레코드 정리 — 완료

- `A  studyez.kr  75.2.85.42` **삭제**
- `A  studyez.kr  99.83.196.71` **삭제**
- `CNAME  www  studyez.kr` — 있으면 그대로 두고, **주황 구름(Proxied)**으로 켠다.
  없으면 만든다. 6단계의 301 리다이렉트가 이 레코드를 통해서 나간다.

apex의 A 레코드를 안 지우면 5단계에서 Pages 커스텀 도메인이 붙지 않는다.

## 4. hosting.kr에서 네임서버 변경 — 완료

실제 할당된 네임서버:

```
apollo.ns.cloudflare.com
princess.ns.cloudflare.com
```

[hosting.kr](https://help.hosting.kr/hc/ko/articles/360035319952) → 로그인 →
**나의 서비스 → 도메인 관리** → `studyez.kr` 체크 → **작업선택 → 네임서버 변경**.
(또는 **도메인 → DNS 설정 → 네임서버 변경**)

기존 `ns1~ns4.hosting.co.kr`을 **모두 지우고** Cloudflare 네임서버 둘을 넣는다.

`.kr` 도메인은 **소유자 인증(이메일 또는 SMS)**을 거쳐야 변경된다. 인증 메일이
`@studyez.kr` 주소로 온다면 지금은 아직 메일이 살아 있으니 문제없다.

반영까지 **최대 24시간**. 그동안 접속이 불안정할 수 있다.

## 5. Pages 커스텀 도메인 — 완료

Cloudflare가 존을 **Active**로 바꾼 뒤에 한다.

Workers & Pages → `study-ez-open` → **Custom domains** → **Set up a domain** →
`studyez.kr` → **Activate domain**.

같은 계정의 존이라 CNAME 레코드는 Cloudflare가 알아서 만든다. 인증서 발급까지
몇 분 걸린다.

SSL/TLS → Overview에서 모드가 **Full (strict)**인지 확인한다.

Pages 화면에서 `studyez.kr`가 **Active / SSL enabled**인 것을 확인했다. Cloudflare
DNS에는 `CNAME @ → study-ez-open.pages.dev`가 Proxied로 생성됐다.

## 6. www → apex 301 — 완료

DNS에 `www`가 **주황 구름**인지 먼저 확인한다(3단계). 프록시를 안 거치면 규칙이
실행되지 않는다.

Rules → **Redirect Rules** → **Create rule**

| | |
|---|---|
Cloudflare의 **Redirect from WWW to root** 템플릿으로 배포했다.

| | |
|---|---|
| Rule name | `www to apex` |
| Match | URI Full wildcard `https://www.*` |
| Target | `https://${1}` |
| Status code | `301` |
| Preserve query string | 켬 |

`https://www.studyez.kr/sample/path?x=1`이
`https://studyez.kr/sample/path?x=1`로 이동하는 것을 실제 브라우저에서 확인했다.

## 7. Supabase URL 교체 — 완료

Supabase → 프로젝트 `dlvruugdigpbtgiwpdgs` → Authentication → URL Configuration

```
Site URL
https://studyez.kr

Redirect URLs
https://studyez.kr/**
https://study-ez-open.pages.dev/**
http://localhost:5173/**
```

Site URL은 **Save changes**, Redirect URLs는 **Save URLs**로 각각 저장한다.
pages.dev를 남겨 두는 이유는 도메인이 반영되는 24시간 동안 그쪽으로도 로그인이
돼야 하기 때문이다. 안정되면 지워도 된다.

위 값 세 개가 저장된 것을 Supabase 화면에서 확인했다.

## 8. API CORS — 2026-08-18 완료

도메인과 무관하게 먼저 해 둘 수 있는 단계라 미리 돌렸다. 기존 origin을 남겨 둔
채로 추가하는 것이라 반영 전에 해도 지금 동작이 깨지지 않는다.
리비전 `studyez-api-00007-qtf`, 트래픽 100%.

`server/.env`:

```
CORS_ALLOWED_ORIGINS=https://study-ez-open.pages.dev,https://studyez.kr
```

`deploy.ps1`이 이 값을 `^|^` 구분자로 넘기므로 쉼표에서 잘리지 않는다.

```powershell
cd server
./deploy.ps1
```

확인한 것 — `https://studyez.kr`와 `https://study-ez-open.pages.dev`는 각각
자기 origin을 돌려받고, 등록되지 않은 origin에는 `access-control-allow-origin`이
아예 안 붙는다. 보호 경로는 그대로 `401`이다.

## 9. 검증

```powershell
# DNS가 Cloudflare로 넘어갔는가
nslookup -type=NS studyez.kr 8.8.8.8

# 메일이 살아 있는가 — 이게 제일 중요하다
nslookup -type=MX studyez.kr 8.8.8.8
nslookup -type=TXT zmail._domainkey.studyez.kr 8.8.8.8

# 프론트
curl.exe -sSI https://studyez.kr
curl.exe -sSI https://www.studyez.kr          # 301 → https://studyez.kr
curl.exe -sSI https://studyez.kr/lectures/x/y # 200 (_redirects가 index.html을 준다)

# API CORS
curl.exe -i -H "Origin: https://studyez.kr" `
  "https://studyez-api-97999573571.asia-northeast3.run.app/api/health"
```

성공 기준:

- MX 셋과 DKIM TXT가 이전과 **같은 값**으로 나온다
- `https://studyez.kr`가 Study_EZ 로그인 화면을 준다
- `access-control-allow-origin: https://studyez.kr`
- 실제로 로그인해서 캘린더가 뜬다 (Supabase redirect까지 확인하는 유일한 방법)

2026-08-18 확인 결과:

- 공용 NS: `apollo.ns.cloudflare.com`, `princess.ns.cloudflare.com`
- Zoho MX 10/20/50, SPF, Zoho 검증 TXT, DKIM 원문 일치
- `https://studyez.kr`에서 Study_EZ 로그인 화면 표시
- Pages 커스텀 도메인 `Active / SSL enabled`
- `www` 경로와 쿼리를 보존한 apex 리디렉션 확인
- 실제 계정 로그인 후 캘린더 확인만 사용자 검증으로 남음

## 나중에 — `/api/*` 같은 도메인으로 (C안)

도메인이 서고 로그인까지 도는 것을 확인한 뒤에 한다. Worker 라우트로
`studyez.kr/api/*`를 Cloud Run에 넘기면 오리진이 하나가 되어
`CORS_ALLOWED_ORIGINS`와 `VITE_API_BASE_URL`을 **둘 다 비울 수 있다.**
`web/README.md`가 적어둔 안이다.

먼저 붙이고 나중에 옮기는 순서인 이유는, 문제가 났을 때 원인이 도메인인지
프록시인지 섞이지 않게 하기 위해서다.
