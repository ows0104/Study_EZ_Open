# 산출물 계약

로컬 러너가 만들고 서버가 받는 것. **이 문서가 두 갈래의 유일한 접점이다.**
파이프라인 안쪽(`run.config.json`, `items.reproduced.json`, `suspects.json` 등)은 서버가
보지 않으므로 자유롭게 바뀐다.

## 강의 식별자

### `uid` — 강의의 진짜 이름

`날짜_교시`만으로는 부족하다. 선택형 과목은 한 교시에 여러 강의가 동시에 열린다.

```
[260303_02] 역사 속의 감염병(김옥주, 이규원)
[260303_02] 질병사 관점에서 신종-재출현 감염병 (송진수)
[260303_02] 건강과 질병(박영수)
```

```
uid = "{날짜_교시}#{제목어간}#{교수들}"
      260303_02#역사속의감염병#김옥주·이규원
```

제목어간은 순번 괄호와 교수 괄호를 뗀 뒤 NFKC·소문자·로마자→아라비아 변환을
거쳐 영숫자·한글만 남긴 것이다(`runner/filenames.py`의 `canonical`).

교수까지 넣는 이유는 한글 괄호가 늘 교수 이름은 아니기 때문이다.
`실습 3(연골과 뼈)`와 `실습 3(근육)`은 둘 다 이름으로 잘못 읽히는데, 넣어 두면
잘못 읽어도 두 강의가 한 편으로 합쳐지지는 않는다.

### `run_id` — 산출물 디렉터리 이름이자 서버의 기본키

`uid`는 길고 특수문자가 섞여 URL·파일명에 안 맞는다. 사람이 읽을 수 있는
짧은 이름을 따로 준다.

```
run_id = "260813_03"           보통은 날짜_교시 그대로
       = "260303_02-73f5"      한 교시에 여러 강의가 열릴 때만 어간 해시 4자
```

**이것이 서버 `lecture` 테이블의 기본키다.** 학기 안에서 유일하고, 같은 파일을
다시 스캔해도 같은 값이 나온다(폴더 전체를 보고 정하므로 결정론적이다).

주의: `run_id`는 **연도를 포함하지만 과목은 포함하지 않는다.** 서버 키는
`(subject, run_id)` 복합이거나 `run_id`에 과목을 접두해야 한다.

### 교시 → 시각

```
시각 = 교시 + 8시     01→09:00  02→10:00  03→11:00  04→점심  05→13:00
```

## 강의 하나당 서버가 받는 것

```
lecture
  subject        "병리학"                    ← 폴더명
  run_id         "260813_03"
  uid            "260813_03#조직재생및수복#김혜령"
  date           "2026-08-13"
  slot           3          slot_end 3       ← 연강이면 slot_end가 크다
  start_time     "11:00"
  title          "조직 재생 및 수복(2)"        ← 표시용 원문
  professors     ["김혜령"]
  author         "최나예"    version 1        ← 필기자와 판
```

`title`은 파일명에서 뽑은 **표시용 원문**이고, 매칭에 쓰인 어간은 서버가 알 필요
없다.

## 파일

| 무엇 | 언제 | 비고 |
|---|---|---|
| 올해 필기 PDF | 매일 | 원본. R2 |
| 작년 필기 PDF | 학기 초 | Pre-Quiz와 예습용. R2 |
| `[<run_id>] <제목>(<교수>).apkg` | Main-Quiz 빌드 후 | Anki 덱. R2 |
| `[<run_id>] <제목>(<교수>) 예습.apkg` | Pre-Quiz 빌드 후 | R2 |
| `slides/<run_id>_s042.png` | 예습 빌드 후 | 근거 슬라이드. 웹 훑기가 읽는다 |

**덱 파일 이름은 자료 파일명과 같은 꼴이다.** 받아 보는 사람이 그 자리에서 어느
강의인지 알아야 한다(`runner.deck.apkg_name`).

```
[260820_03] 소아질환의 병태생리(2) 소아기 특이 질환 1(김은나).apkg
[260824_01] 종양의 병태 생리(2) 종양의 분자생물학(1)(전윤경) 예습.apkg
```

**예습 덱의 이름은 올해 강의로 선다.** 작년 필기로 만들지만 학생은 캘린더를 보고
예습하므로, 작년 날짜와 작년 제목이 붙은 파일은 어느 강의의 것인지 안 보인다.
그 올해 강의가 무엇인지는 `prequeue`가 `pre_target.json`에 적어 둔다 — 아직 필기가
없는(시간표에만 있는) 강의도 거기서 온다.

이름은 guid와 무관하다. guid의 씨앗은 `deck_id`(`p260820_03`)이고 그건 안 바뀐다 —
바꾸면 Anki가 이미 받아 간 카드를 전부 새 노트로 본다.

꼬리가 ` 예습`인가가 두 갈래를 가른다(옛 이름 `_pre`·`_예습`도 받는다).
**한 디렉터리에 둘이 같이 있을 수 있다** — 올해 필기로 복습 덱을 만든 강의가
내년에는 「작년 필기」가 되어 같은 자리에서 예습 덱을 낳는다.

슬라이드는 **예습 쪽만** 올린다. 그 이미지를 읽는 곳이 서버에 한 군데뿐이고
(웹 훑기의 근거 그림) 편당 12~27MB이기 때문이다. 파일명 끝의 `_s042`에서 서버가
슬라이드 번호를 읽으므로(`server/app/naming.py`) 그 꼴을 깨면 안 된다.

**전부 로그인 뒤에만 내보낸다.** 제3자 저작물이다.

## `run.meta.json` — 덱 하나의 요약

`quizgen`는 이 파일을 만들지 않는다. 파이프라인 안쪽(`run.config.json`·
`items.reproduced.json`·`suspects.json`)을 읽어 이 모양으로 옮기는 것은
[runner/deck.py](../runner/deck.py)의 `contract()`다. 실물은
[samples/run.meta.sample.json](samples/run.meta.sample.json)에 있다.

```json
{ "lecture_id": "260820_03", "lecture_title": "소아질환의 병태생리(2) …",
  "deck_id": "p260820_03",
  "deck_name": "병리학::소아질환의 병태생리(2) 소아기 특이 질환 1",
  "deck_file": "p260820_03.apkg",
  "built_at": "2026-08-23T00:39:38",
  "pipeline": "quizgen",
  "attempt": { "kind": "main", "version": "260827-2300",
               "cards_sha256": "a03dd97c…" },
  "verified": { "notes": 88, "cards": 92, "media": 46, "decks": 2,
                "missing_media": [] },
  "item_count": 88,
  "format": { "basic": 75, "cloze": 2, "ox": 6,
              "image_occlusion": 3, "image_basic": 2 },
  "sources": { "lecture": 79, "jokbo": 9 },
  "importance": { "core": 63, "detail": 25 },
  "exam_hit": 4,
  "review_flagged": 13,
  "review_flags": { "off_plan": 3, "points_at_source": 2 },
  "reproduce": { "same": 75, "partial": 4, "different": 4, "없음": 5 },
  "reproduce_defects": [],
  "slides_total": 46, "slides_used": [...], "slides_unused": [...],
  "untouched_slides": [], "objectives_without_card": [],
  "strategy": "annotation", "strategy_why": "교수 교체(김은나) → 필기 중심" }
```

관리자 화면과 `runner.gate`가 이걸로 "배포해도 되는가"를 판단한다.

- **`attempt`는 이 덱을 만든 시도다**(2026-09-15부터 · `docs/runs-layout.md` 5단계).
  산출물이 `runs/<편>/main/<판>/` 로 갈린 뒤 생겼다. **`null` 이면 옛 모양**이다 —
  시도가 강의 폴더에 그대로 있어서 판이라는 것이 없다. 이 값이 있어야 「사람이 고른
  판」과 「실제로 올라간 판」을 맞대 볼 수 있다(`runner.chosen.verdict`)
- **`verified`는 apkg를 다시 열어 센 값이다.** `item_count`와 어긋나면 덱이 내용과
  다른 것을 담고 있다는 뜻이고, 검문이 막는 몇 안 되는 것 중 하나다
- **`reproduce`가 `same`이 아니어도 나쁜 카드는 아니다.** 질문만 보고 다시 푼
  결과이고, 눈가리개 세션이 그 지식을 몰랐을 수 있다. 문항 자체의 결함으로 갈린
  것은 빌드가 이미 뺐고, 그래도 남아 있으면 `reproduce_defects`에 뜬다
- **`review_flagged`는 개수, `review_flags`가 종류다.** 사람을 부르는 신호는 종류에 있다
- `slides_unused`는 카드가 없는 슬라이드 전부(표지·학습목표가 여기 든다).
  진짜 누락 신호는 선언된 건너뜀을 이미 뺀 `untouched_slides` 쪽이다
- `strategy`·`strategy_why`는 복습에만 붙는다
- `web_items`·`web_excluded`·`slides_exported`·`web_without_explanation`은
  **두 갈래 다** 붙는다(2026-08-31부터. 그 전 편에는 복습 쪽이 없다)

`lecture_id` 필드 이름은 역사적인 것이고 값은 `run_id`다. `deck_id`는 quizgen의
ID(`p260820_03`)이고 **그쪽이 guid의 씨앗이다** — 바꾸면 Anki가 이미 받아 간
카드를 전부 새 노트로 본다.

## `pre_items.final.json` — 웹에서 훑는 예습 카드

배급의 기본은 `.apkg`다. 이 JSON은 그 옆의 갈래 — Anki를 안 깐 자리에서 훑어보는
화면이 읽는다. **자유회상 카드라 보기가 없고, 채점은 서버가 아니라 본인이 한다.**

```json
{ "lecture_id": "250825_01",
  "deck_id": "p250825_01",
  "generated_by": "quizgen.prequiz",
  "items": [
    { "id": "c001",
      "qtype": "basic",                     // basic | cloze | ox
      "stem": "Proto-oncogene 과 oncogene 은 어떻게 다른가?",
      "answer": "- proto-oncogene: …
- oncogene: …",
      "explanation": "...",
      "focus": "spine",                     // spine|vocabulary|mechanism|clinical|repeated
      "card_type": "term",                  // term|abbrev|mechanism|taxonomy|clinical|number|…
      "exam_hit": false,
      "slide_no": 34,
      "source_type": "lecture",             // lecture | annotation | note | jokbo
      "source_anchor": "lecture_text",      // 어느 채널을 근거로 삼았나
      "flags": [] } ] }
```

지켜야 할 것:

- **`answer`·`explanation`을 문항과 함께 내려보내지 마라.** 답을 편 사람만
  `POST .../prequiz/reveal`로 받아 간다. 같이 보내면 펴 보기 전에 정답이 보이고,
  그러면 `quiz_attempt`의 「알고 있었다」가 아무것도 뜻하지 않는다
- **채점하지 마라.** `POST .../prequiz/grade`는 `correct` 불리언을 받아 적을 뿐이다.
  답이 여러 줄 산문일 때가 많아 문자열로 재면 전원이 틀린다
- **`focus`는 등급이 아니라 이유다.** 예습 카드는 전부 「꼭 반드시」이고, 등급을
  두면 그 축이 흐려진다. 「왜 이것이 꼭 반드시인가」를 담는다
- `cloze`의 `stem`은 이미 빈칸으로 펴져 있다. `{{c1::…}}`은 Anki 문법이라
  `runner.deck.contract`가 `[____]`(힌트가 있으면 `[힌트]`)로 바꾼다
- **그림 카드는 여기 없다.** 앞면이 이미지라 텍스트만으로는 물음이 성립하지 않는다.
  apkg에는 그대로 있고, 몇 장이 빠졌는지는 `pre_run.meta.json`의 `web_excluded`가 든다
- `slide_no`로 근거 슬라이드를 띄우려면 `slides/`도 함께 올라가야 한다
  (`<run_id>_s042.png`. 서버가 파일명 끝에서 번호를 읽는다)

### 복습도 같은 모양을 낸다 — 다만 아직 아무도 안 읽는다

2026-08-31부터 복습 run 도 `main_items.final.json`을 낸다(`generated_by`가
`quizgen.main`). 모양은 위와 같고 `focus` 자리만 갈린다 — 예습은 이유(`reason`),
복습은 등급(`importance`)이다.

`publish`가 `PUT …/main-items`로 올리고 서버는 `main_item` 표에 넣는다. 화면은
`/mainquiz/<과목>/<run_id>`이고 예습과 **같은 화면**이다(`web/src/lecture/QuizPage`).

**이 줄이 붙기 전에 구운 복습 39편에는 이 파일도 `slides/`도 없다.** 쓰려면 그
편들을 다시 돌려야 하고, 그때까지 그 강의들의 `mainquiz`는 `null`이라 화면이
웹 풀이를 아예 안 그린다 — 덱만 있는 편과 같은 자리다.

무엇이 나오는지는 그 39편으로 미리 쟀다(2026-08-31):

    웹으로 갈 수 있는 카드   3,762장 중 3,384장 (90%)
    편별                     중앙값 94장 · 범위 27~143장  (예습은 28장)
    빠지는 것                전부 그림 카드. 비율이 낮은 편 넷은 모두 실습이다
    해설이 있는 것           54%  (예습은 100%)

마지막 줄이 지을 때 걸리는 자리다 — 웹 풀이는 틀렸을 때 해설을 보여 주는 화면인데
복습은 그 자리가 절반이 빈다. Anki는 앞뒤만 보므로 지금까지 아쉬울 일이 없었다.
`web_without_explanation`이 편마다 그 수를 든다.

**슬라이드는 갈래를 가른 kind로 올라간다** — 예습이 `media`, 복습이 `main_media`
(`server/app/models.py`의 `SLIDE_KINDS`). 예습 슬라이드는 작년 run에서 와 놓고
올해 강의의 이름으로 올라가 있어서, 한 kind에 몰면 같은 `slide_no`가 둘이 되고
오답 해설이 조용히 엉뚱한 슬라이드를 띄운다. `server/tests/test_quiz_kinds.py`가
그 자리를 지킨다.

파이프라인 안쪽의 `items.reproduced.json`은 이것과 **다른 모양**이다(카드 그대로).
서버는 그걸 보지 않는다.

## 예습 링크

```
preview
  run_id
  provider       "chatgpt"
  share_url      "https://chatgpt.com/share/..."   ← 모두에게 보인다. 퀴즈의 기본 링크
  conversation_url                                  ← 당분간 관리자만
```

`conversation_url`(`/c/`)을 지금 학생에게 안 내보내는 것은 **원칙이 아니라 그
링크가 아직 불안정하기 때문**이다. 최종적으로는 학생에게도 준다 — 대화를 열어
이어서 질문할 수 있는 게 예습의 값어치다. 그러니 스키마에서 빼지 말고 담아 두되,
지금은 일반 사용자 응답에서만 가린다.

## 사용자별 데이터 — 하나뿐이다

`quiz_attempt` 한 표다. 웹에서 예습 카드를 훑은 사람이 카드마다 「알고 있었다 /
몰랐다」를 찍은 기록이고, **그 값은 본인의 판정이지 서버의 판정이 아니다.**
화면이 그것을 서버 판정처럼 그리면 안 된다.

나머지는 전부 읽기 전용이다. 복습 덱은 `.apkg`로 내려받아 Anki에서 풀고, 그
결과는 서버에 남지 않는다.

## 무엇이 아직 움직이는가

| | 상태 |
|---|---|
| `uid` · `run_id` 규칙 | **고정.** 이 문서가 계약이다 |
| `run.meta.json` | 고정 |
| `pre_items.final.json` | 고정. 실물은 [samples/](samples/) |
| `.apkg` · PDF · `slides/` | 고정 |
| `run.config.json`·`prep.json`·`items.reproduced.json`·`suspects.json` | **서버가 보지 않는다.** quizgen 안쪽이라 자유롭게 바뀐다 |

서버 쪽에서 파이프라인 내부 파일을 읽고 싶어지면 먼저 이 문서에 올려라.
