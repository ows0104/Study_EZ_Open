# Study_EZ 서버

**아무것도 만들지 않는다.** 로컬 러너가 만든 것을 받아 배급한다. 워커도, 작업
큐도, 과금도 없다.

```
app/
  config.py     환경 변수 하나로 모인다
  database.py   SQLAlchemy 엔진
  models.py     표 14개. 사용자가 쓰는 것은 quiz_attempt·main_attempt·asset_grab 셋뿐이다
  auth.py       Supabase JWT 검증 + is_admin 불리언
  storage.py    R2 서명 URL
  naming.py     NFC·정규화. runner/filenames.py와 같은 규칙이다
  matching.py   시간표 칸 ↔ 필기에서 읽어 낸 강의
  cli.py        init-db · seed-timetable (data/timetable/) · purge-artifacts
  preview_links.py  예습 제공자와 링크 형식의 단일 검증점
  routes/       me · timetable · lectures · prequiz · admin · prequiz_jobs · local_storage
                prequiz.py 는 학생이 푸는 문항 — **예습·복습 두 갈래가 이 한 파일이다**.
                prequiz_jobs.py 는 러너가 집어 가는 일감이다
tests/          검사 일곱. pytest 가 아니라 스크립트다 — 아래 「검사」를 보라
```

테스트는 pytest 가 아니라 스크립트다 — **파일마다 프로세스가 따로여야 한다**
(아래 「검사」에 이유가 있다).

```bash
.venv/Scripts/python.exe -m tests
```

## 띄우기

```bash
python -m venv .venv && .venv/Scripts/pip install -r requirements.txt
cp .env.example .env          # 값을 채운다
python -m app.cli init-db
python -m app.cli seed-timetable          # data/timetable/의 최신 학기 파일
python -m uvicorn app.main:app --reload
```

`ENVIRONMENT=local-test`면 R2 대신 디스크를 쓰고 Supabase 검증을 건너뛴다.
그때 통하는 토큰은 `local-test-token` 하나이며, **배포된 서버에서는 통하지
않는다** — 로그인 필수라는 규칙에 구멍이 없다는 뜻이다.

## 검사

```bash
.venv/Scripts/python.exe -m tests                 # 일곱 개 전부 (파일마다 새 프로세스)
.venv/Scripts/python.exe -m tests smoke           # 이름에 그 글자가 든 것만
```

| | |
|---|---|
| `test_smoke` | 강의 한 편이 통과하는 전 과정 |
| `test_matching` | 한 교시에 여러 강의가 열릴 때 |
| `test_quiz_kinds` | 예습·복습이 서로를 안 덮는가 |
| `test_samples` | 표본 산출물이 계약과 맞는가 |
| `test_details_split` | 시간표 `details` 를 제목과 교수로 가르기 |
| `test_source_version` | 산출물의 판 번호 |
| `test_spotter_reports` | 땡시 제보·게시판 |

SQLite로 돈다. Postgres 고유 기능을 쓰지 않는다는 것도 같이 확인된다.

**`pytest` 로는 안 돈다.** 파일마다 import 시점에 자기 `DATABASE_URL` 을 세우고
`app.database` 의 모듈 수준 엔진을 만들기 때문에, 한 프로세스에 모으면 먼저 import
된 것의 DB 를 나머지가 같이 쓴다. 그래서 파일마다 프로세스가 따로여야 한다.

예전에는 `pytest server/tests` 가 **`no tests ran` 과 함께 종료 코드 0** 을 냈다 —
초록색이 「통과」인지 「안 돌았다」인지 구별되지 않았다. 지금은 `conftest.py` 가
그 자리에서 이 문서를 가리키고 0 이 아닌 값으로 끝낸다.

## 로컬 러너가 부르는 것

전부 `Authorization: Bearer $RUNNER_TOKEN`이다. 러너는 사람이 아니라
스크립트라서 Supabase 세션이 없다.

| | |
|---|---|
| `POST /api/admin/lectures` | 강의 목록 upsert. 시간표 칸에 자동으로 붙는다 |
| `POST /api/admin/lectures/{과목}/{run_id}/uploads` | 서명 URL 발급 (배열) |
| `POST …/uploads/complete` | 올라온 것을 확인하고 `asset`에 남긴다 |
| `PUT …/run-meta/{main\|pre}` | `run.meta.json` 통째로 |
| `PUT …/pre-items` | `pre_items.final.json` 통째로. 부분 갱신이 아니라 교체 |
| `PUT …/main-items` | `main_items.final.json` 통째로. 같은 규칙, 표만 다르다 |
| `PUT …/preview` | 예습 링크 |
| `GET /api/admin/previews` | 저장된 예습 링크 전부. **여기만 읽는 쪽이다** |

`GET …/previews`만 방향이 반대다. 예습을 하는 것은 사람이고 사람은 `/admin`
화면에서 링크를 저장하므로, 그것을 로컬이 되읽어 Pre-Quiz를 만든다
(`python -m runner prequeue`). `/api/admin/overview`로 갈음할 수 없다 —
그쪽은 `require_admin`이라 Supabase 세션이 있어야 한다.

**파일은 서버를 거치지 않는다.** Cloud Run의 요청 본문 상한(32MB)이 강의록
PDF보다 작아서, 서버는 키를 정하고 올라온 것을 확인만 한다.

```
1. POST …/uploads           [{kind, filename, sizeBytes, contentType}, …]
                            → [{objectKey, uploadUrl}, …]
2. PUT  uploadUrl           파일 본문. Content-Type은 1에서 보낸 값 그대로
3. POST …/uploads/complete  같은 목록 → {stored, missing}
```

2의 헤더는 선택이 아니다. 서명이 `content-type;host`를 덮으므로 값이 다르거나
빠지면 R2가 `SignatureDoesNotMatch`로 막는다. 길이도 직접 실어야 한다 — 파일
객체를 그대로 주면 클라이언트가 chunked로 보내고 그건 서명과 맞지 않는다.

키가 `(subject, run_id, kind, filename)`으로 결정되므로 중간에 끊기면 처음부터
다시 돌리면 된다. `missing`이 비어 있지 않으면 그 파일은 세지 않는다.

`kind`는 산출물 계약의 다섯 가지뿐이다 — `notes_current`, `notes_prev`,
`main_apkg`, `pre_apkg`, `media`. 다른 값은 422로 막힌다. **계약에 없는 파일이
필요하면 추측해서 맞추지 말고 `docs/artifact-contract.md`를 먼저 고쳐라.**

## 지켜야 할 것이 어디에 있나

| | |
|---|---|
| **로그인 필수** — 관문은 이것 하나다 | `auth.py`. 모든 읽기 경로가 `get_current_user`를 지난다 |
| 키는 `(subject, run_id)` 복합 | `models.py` 전부, `routes/common.py`의 `lecture_or_404` |
| `/c/`는 설정으로 열고 닫는다 | `routes/lectures.py`의 `_preview_payload` |

파일이 서명 URL로 나가는 것은 저작권 규정이 아니라 **R2 버킷이 비공개이기
때문이다.** 공개 버킷으로 바꾸면 로그인을 지나지 않고도 파일이 열려서 "로그인
필수"가 화면에만 걸린 말이 된다. 수명은 `STUDYEZ_SIGNED_URL_TTL`(기본 한 시간).

`/c/` 대화 링크는 **결국 모두에게 줄 것이다.** 지금 관리자에게만 나가는 것은
그 링크가 아직 불안정해서이고, 안정되면 `STUDYEZ_SHOW_CONVERSATION_URL=true`
하나면 된다. 퀴즈를 만들 때 쓰는 기본 링크는 `share_url` 쪽이다.

Pre-Quiz는 **웹 풀이가 먼저다**(2026-08-23 관리자 지시). 화면에서 Pre-Quiz를
누르면 `routes/prequiz.py`가 내는 문항이 전용 창에 뜨고, apkg는 그 옆의 내려받기
버튼으로 내려갔다. 사용자별 기능을 붙일 자리도 여기다 — `quiz_attempt`가 그
사람에 대해 서버가 아는 유일한 것이다.

정답은 문항과 함께 내려보내지 않는다 — `GET …/prequiz`에 `answer`도
`explanation`도 없고, 편 사람만 `reveal`로 받아 간다. **채점은 서버가 아니라
본인이 한다**(자유회상이라 대조할 문자열이 없다).

## 마이그레이션 도구가 없는 이유

표가 아홉이고 고치는 사람이 한 명이다. Alembic이 얹는 무게가 그것으로 막는
사고보다 크다. 스키마가 바뀌면 `init-db`로 다시 만든다.

**다만 `init-db`는 없는 표만 만들고 있는 표는 안 고친다.** `create_all`이 그렇다.
열을 하나 더한 경우, 이미 있는 DB에는 손으로 넣어야 한다. 안 넣으면 그 열을 읽는
경로만 500으로 죽는다.

| 언제 | 무엇 | 어떻게 |
|---|---|---|
| 2026-08-17 | `profile.preview_prompt` — 사용자별 예습 프롬프트 | 아래 SQL |
| 2026-08-18 | `user_preview` 표 — 사람마다 가진 개인 예습 대화 | `init-db` |
| 2026-08-25 | `user_preview.provider` — 개인 링크의 ChatGPT·Gemini·Claude 구분 | `init-db` (`ADDED_COLUMNS`) |

**표가 새로 생긴 것은 `init-db`로 된다.** `create_all`이 없는 표는 만든다 —
못 고치는 것은 이미 있는 표의 열뿐이다.

```sql
ALTER TABLE profile ADD COLUMN preview_prompt TEXT NOT NULL DEFAULT '';
```
