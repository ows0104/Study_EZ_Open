# server — FastAPI · Cloud Run (studyez-api)

**두 제품이 만나는 유일한 자리다.** 계정·인증·R2 서명이 여기 하나뿐이다.

    무엇을 고치면 어느 파일인가    ../docs/map.md §2
    검사                          .venv/Scripts/python.exe -m tests    (pytest 가 아니다)
    경로 계약                      tests/test_routes_golden.py          61줄
    배포                          deploy.ps1 을 손으로
    권한 · 어디서나 미는 함정       ../CLAUDE.md

**`quizgen` 도 `runner` 도 import 하지 않는다.** 그 상태를 `scripts/map_numbers.py`
가 센다 — 0 이 아니면 2로 끝난다. 여기에 파이프라인을 끌어들이지 마라.

## 검사가 pytest 가 아닌 것은 사정이 있어 고른 것이다

다섯 파일이 **import 시점에** 자기 `DATABASE_URL` 을 세우고 `app.database` 의 모듈
수준 엔진을 만든다. 한 프로세스에 모으면 먼저 import 된 것의 DB 를 나머지가 같이 쓴다.
**한 파일에 한 프로세스여야 한다** — 그래서 이 폴더는 스크립트다.

```bash
cd server
.venv/Scripts/python.exe -m tests            # 전부
.venv/Scripts/python.exe -m tests smoke      # 이름에 그 글자가 든 것만
```

`pytest server/tests` 는 **아무것도 수집하지 않고 0을 돌려줬다.** 그것이 「통과」로
읽히는 것을 막기 위해 `conftest.py` 가 그 자리에서 말하고 0 이 아닌 값으로 끝낸다.
자세한 것은 `tests/__main__.py` 와 `conftest.py` 머리에 있다.

## 경로를 바꾸면 넷이 같이 본다

`web/` 16개 · `runner/` 9개 · `spotter/scripts/` 10개 · `bridge/` 2개가 이 서버를
부른다. **가로로는 아무도 서로를 안 부르므로** 경로 목록이 그대로면 한쪽만 고쳐도 된다.

```bash
cd server && .venv/Scripts/python.exe -m tests.test_routes_golden
```

땡시 경로는 2026-09-14 에 1,008줄 한 파일에서 `routes/spotter/` 일곱 파일로 갈랐다.
**그때 경로 목록이 한 줄도 안 달라졌다** — 그것이 갈라도 된다는 증거였다.

## `.env` 가 프로덕션이다

`config.py` 는 `DATABASE_URL` 이 환경에 없을 때만 `.env` 를 읽는다. 그래서
`python -m app.cli …` 를 그냥 치면 **운영 DB 에 쓴다.** 로컬 사본을 치려면
`DATABASE_URL` 을 윈도우 경로로 덮어써서 부른다.

마이그레이션 도구는 두지 않았다 — 이유와 칼럼을 늘리는 법은 `app/cli.py` 머리에 있다.

## push 는 이쪽을 배포하지 않는다

프론트만 Cloudflare Pages 가 저절로 낸다. **API 는 `deploy.ps1` 을 손으로** 돌려야 한다.
밀기 전에 `openapi.json` 과 라우트를 맞대 본다.
