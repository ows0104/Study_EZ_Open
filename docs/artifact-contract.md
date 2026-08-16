# 산출물 계약

로컬 러너가 만들고 서버가 받는 것. **이 문서가 두 갈래의 유일한 접점이다.**
파이프라인 안쪽(`structure.json`, `blueprint.json`, `suspects.json` 등)은 서버가
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
거쳐 영숫자·한글만 남긴 것이다(`studyez/filenames.py`의 `canonical`).

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
| `<강의>.apkg` | Main-Quiz 빌드 후 | Anki 덱. R2 |
| `<강의>_예습.apkg` | Pre-Quiz 빌드 후 | R2 |
| `media/*.png` | 빌드 후 | 슬라이드 이미지. 웹 풀이의 오답 해설이 쓴다 |

**전부 로그인 뒤 짧은 수명의 서명 URL로만 내보낸다.** 제3자 저작물이다.

## `run.meta.json` — 덱 하나의 요약

```json
{ "lecture_id": "260812_01", "lecture_title": "병리학 소개",
  "deck_name": "병리학::[260812_01] 병리학 소개",
  "built_at": "2026-08-16T12:23:30",
  "verified": { "notes": 80, "cards": 80, "media": 24 },
  "item_count": 80,
  "format": { "basic": 76, "cloze": 4, "jokbo": 16, "occlusion": 0 },
  "importance": { "core": 40, "detail": 40 },
  "sources": { "lecture": 64, "jokbo": 16 },
  "exam_hit": 28, "stamped": 39, "trap_notes": 24,
  "review_flagged": 2,
  "slides_used": [...], "slides_unused": [...] }
```

관리자 화면이 이걸로 "배포해도 되는가"를 판단한다. **`review_flagged`가 0이
아니면 사람이 카드 뒷면 경고 박스를 확인해야 한다.** `slides_unused`는 카드가
하나도 없는 슬라이드다.

`lecture_id` 필드 이름은 역사적인 것이고 값은 `run_id`다.

## `pre_items.final.json` — 웹 풀이 화면이 읽는 것

```json
{ "lecture_id": "250820_02",
  "items": [
    { "id": "p001",
      "qtype": "mcq",                       // mcq | short | ox
      "stem": "...해당하지 **않는 것은**?",   // 마크다운 강조가 들어간다
      "choices": ["...", "...", "...", "...", "..."],   // mcq는 정확히 5개, 그 외 null
      "answer": "3",                        // mcq: 1-based 인덱스 문자열
                                            // short: 정답 텍스트
                                            // ox: "O" | "X"
      "focus": "must_know",                 // must_know | core | context
      "exam_hit": true,
      "slide_no": 6,
      "source_type": "lecture",             // lecture | jokbo
      "source_anchor": "본문 '4가지 카테고리' 목록의 1)~4)항",
      "explanation": "...",
      "objective_id": "obj_1",
      "retrieval_target": "...",
      "flags": [] } ] }
```

지켜야 할 것:

- **`stem`의 `**강조**`를 렌더링하라.** 부정형 발문을 놓치지 말라고 넣은 것이라
  지우면 안 된다
- `short`의 채점은 문자열 완전일치가 아니다. `explanation` 첫 줄에 허용 표기가
  적혀 있다(예: "Leber hereditary optic neuropathy / LHON / Leber 유전성 시신경병증
  어느 표기든 정답이다")
- `slide_no`로 근거 슬라이드를 띄우려면 `media/`도 함께 올라가야 한다

`items.final.json`(Main-Quiz)은 같은 뼈대에 Anki 전용 필드가 더 붙는다. 웹에서
풀지 않으므로 서버는 저장만 하면 된다.

## 예습 링크

```
preview
  run_id
  provider       "chatgpt"
  share_url      "https://chatgpt.com/share/..."   ← 모두에게 보인다
  conversation_url                                  ← 관리자만. API 응답에서 뺀다
```

## 사용자별 데이터 — 이 사이트에서 유일하다

```
quiz_attempt
  user_id  run_id  item_id  answered  correct  answered_at
```

Pre-Quiz 웹 풀이의 채점 결과. 강의 상세가 **"오늘 놓친 것 3개"**를 보여주는 데
쓴다. 이것 말고는 전부 읽기 전용이다.

## 무엇이 아직 움직이는가

| | 상태 |
|---|---|
| `uid` · `run_id` 규칙 | **고정.** 이 문서가 계약이다 |
| `run.meta.json` | 고정 |
| `pre_items.final.json` | 고정 (`.claude/skills/prequiz/references/item.schema.json`) |
| `.apkg` · PDF · `media/` | 고정 |
| `structure.json`·`blueprint.json`·`suspects.json` | **서버가 보지 않는다.** 자유롭게 바뀐다 |

서버 쪽에서 파이프라인 내부 파일을 읽고 싶어지면 먼저 이 문서에 올려라.
