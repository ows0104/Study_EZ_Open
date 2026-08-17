# Study_EZ 서버

**아무것도 만들지 않는다.** 로컬 러너가 만든 것을 받아 배급한다. 워커도, 작업
큐도, 과금도 없다.

```
app/
  config.py     환경 변수 하나로 모인다
  database.py   SQLAlchemy 엔진
  models.py     표 9개. 사용자가 쓰는 것은 quiz_attempt 하나뿐이다
  auth.py       Supabase JWT 검증 + is_admin 불리언
  storage.py    R2 서명 URL
  naming.py     NFC·정규화. studyez/filenames.py와 같은 규칙이다
  matching.py   시간표 칸 ↔ 필기에서 읽어 낸 강의
  cli.py        init-db · seed-timetable
  routes/       timetable · lectures · prequiz · admin · local_storage
tests/          test_smoke.py · test_matching.py
```

## 띄우기

```bash
python -m venv .venv && .venv/Scripts/pip install -r requirements.txt
cp .env.example .env          # 값을 채운다
python -m app.cli init-db
python -m app.cli seed-timetable "…/2026_본1_2학기_시간표.json"
python -m uvicorn app.main:app --reload
```

`ENVIRONMENT=local-test`면 R2 대신 디스크를 쓰고 Supabase 검증을 건너뛴다.
그때 통하는 토큰은 `local-test-token` 하나이며, **배포된 서버에서는 통하지
않는다** — 로그인 필수라는 규칙에 구멍이 없다는 뜻이다.

## 검사

```bash
.venv/Scripts/python.exe -m tests.test_smoke      # 강의 한 편이 통과하는 전 과정
.venv/Scripts/python.exe -m tests.test_matching   # 한 교시에 여러 강의가 열릴 때
```

SQLite로 돈다. Postgres 고유 기능을 쓰지 않는다는 것도 같이 확인된다.

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
| `PUT …/preview` | 예습 링크 |

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

Pre-Quiz는 **apkg 배급이 먼저다.** 웹 풀이(`routes/prequiz.py`, `quiz_attempt`)는
그 옆의 갈래로 남아 있고 화면에서도 뒤에 있다. 사용자별 기능을 본격적으로 붙일
때 여기서 이어 가면 된다. 그때까지도 정답은 문항과 함께 내려보내지 않는다 —
`GET …/prequiz`에 `answer`도 `explanation`도 없고 채점은 서버가 한다.

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

**표가 새로 생긴 것은 `init-db`로 된다.** `create_all`이 없는 표는 만든다 —
못 고치는 것은 이미 있는 표의 열뿐이다.

```sql
ALTER TABLE profile ADD COLUMN preview_prompt TEXT NOT NULL DEFAULT '';
```
