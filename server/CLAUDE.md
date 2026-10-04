# server — FastAPI · Cloud Run (studyez-api)

**두 제품이 만나는 유일한 자리다.** 계정·인증·R2 서명이 여기 하나뿐이다.

    무엇을 고치면 어느 파일인가    ../docs/map.md §2
    검사                          .venv/Scripts/python.exe -m tests    (pytest 가 아니다)
    경로 계약                      tests/test_routes_golden.py          69줄
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

`web/` 23개 · `runner/` 9개 · `spotter/scripts/` 10개 · `bridge/` 2개가 이 서버를
부른다. **가로로는 아무도 서로를 안 부르므로** 경로 목록이 그대로면 한쪽만 고쳐도 된다.

```bash
cd server && .venv/Scripts/python.exe -m tests.test_routes_golden
```

땡시 경로는 2026-09-14 에 1,008줄 한 파일에서 `routes/spotter/` 일곱 파일로 갈랐다.
**그때 경로 목록이 한 줄도 안 달라졌다** — 그것이 갈라도 된다는 증거였다.

2026-09-21 에 한 줄이 늘었다 — `GET /api/lectures/…/deck-job`. **관리자 경로를
학생에게 열어 주는 대신 주는 칸을 덜어 낸 경로를 세웠다.** 같은 표를 읽지만
`job_row` 는 누가 눌렀는지(남의 이메일) · 어느 일꾼이 잡았는지 · 왜 실패했는지 ·
줄에서 몇 번째인지까지 싣는다. 덜어 낸 것은 `watch_row` 고, **덜어 냈다는 것은
세어 봐야 사실이 된다**(`tests/test_deck_watch.py` — 화면에서 안 그리는 것과
응답에 안 싣는 것은 다른 일이다).

## 복습 일정은 `app/srs.py` 하나다

2026-09-18 에 웹 풀이가 망각곡선으로 돌게 되면서 생겼다(관리자 지시). **안키의
SM-2 를 그대로 옮긴 순수 함수 모듈이다** — DB 도 시계도 안 들고 `now` 를 받는다.

    app/srs.py              간격을 정하는 유일한 자리. 상수까지 안키 기본값이다
    routes/prequiz.py       그것을 표에 옮겨 적고, 되돌릴 값을 적어 둔다
    tests/test_srs.py       사다리를 시각을 밀어 가며 잰다 (순수 함수라 된다)
    tests/test_quiz_srs.py  그것이 표와 경로를 지나 오는가 · 되돌리기

**화면에도 일정 계산을 두지 않았다.** 버튼에 적을 「언제 다시 나오나」까지
`reveal` 이 `srs.preview` 로 재서 보낸다. 두 언어에 같은 사다리를 적으면 갈라진다.

**칼럼을 늘렸으므로 배포 전에 `init-db` 를 지나야 한다**(`ADDED_COLUMNS`). 안 지나면
운영 DB 에 `state` 가 없어 웹 풀이가 통째로 500 이다.

## 표를 새로 세우면 배포 전에 `init-db` 를 지난다

`create_all` 은 **없는 표만** 세운다. 그래서 새 표는 `init-db` 한 번으로 서지만,
그 전에 코드가 먼저 올라가면 그 표를 읽는 경로가 500 이다. 순서가 있다 —
**`init-db` 먼저, 배포는 그다음.**

2026-09-19 에 `preview_open` 이 그렇게 섰다 — 예습 링크를 **우리 화면에서** 누른
횟수다. 그 주소는 AI 서비스의 것이라 서버를 안 지나므로, 누르는 자리가 알려 주지
않으면 영영 못 센다. 적는 쪽은 실패해도 링크를 막지 않는다(`record_preview_open`).

**표가 선 날부터만 찬다.** 그 전은 0으로 보이므로 이용현황이 `opensSince` 를 같이
내보내 화면이 그 0을 가른다.

같은 날 `user_visit`(접속 기록)도 세웠다가 **몇 시간 만에 걷어냈다**(관리자 —
「접속기록표는 없애자. 어차피 마지막 접속으로 알 수 있다」). 운영 DB 의 표는
`DROP TABLE` 로 지웠다(줄 하나였다). 이용현황의 `lastAt` 이 그 답을 이미 한다.

2026-09-23 에 `card_edit` 가 그렇게 섰다 — 관리자가 「카드 검토」에서 내린 판정이다.
문지기가 결함 카드를 막지 않고 올리게 되면서 생겼다(`routes/cards.py` 머리).
**러너가 문항을 통째로 갈아 끼우므로** `admin._put_items` 가 갈아 끼울 때마다 이 표를
다시 얹는다 — 문항 표에만 쓰면 다음 쓸기가 고친 것을 조용히 되돌린다.

2026-10-04 에 `notice` 가 그렇게 섰다 — 공지사항이다(`routes/notices.py`). 읽기는
승인된 사람, 쓰기는 관리자. 읽음 표시는 서버에 없다 — 브라우저가 마지막으로 본
번호만 든다(`web/src/notices/seen.ts`).

## `.env` 가 프로덕션이다

`config.py` 는 `DATABASE_URL` 이 환경에 없을 때만 `.env` 를 읽는다. 그래서
`python -m app.cli …` 를 그냥 치면 **운영 DB 에 쓴다.** 로컬 사본을 치려면
`DATABASE_URL` 을 윈도우 경로로 덮어써서 부른다.

마이그레이션 도구는 두지 않았다 — 이유와 칼럼을 늘리는 법은 `app/cli.py` 머리에 있다.

## push 는 이쪽을 배포하지 않는다

프론트만 Cloudflare Pages 가 저절로 낸다. **API 는 `deploy.ps1` 을 손으로** 돌려야 한다.
밀기 전에 `openapi.json` 과 라우트를 맞대 본다.
