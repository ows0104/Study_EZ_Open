# 무엇을 고치려면 어디를 보는가

**이 문서의 목적은 「전체를 읽지 않아도 되게」 하는 것이다.** 아래 표에서 일감을
찾아 그 줄의 경로만 주면 된다. 왜 그래도 되는지는 §3(연결부)에 있다 — 덩이끼리
닿는 자리가 넷뿐이고 전부 좁다.

> **2026-09-14 에 문맥도 같이 갈랐다.** 덩이마다 자기 `CLAUDE.md` 가 있고
> ([quizgen](../quizgen/CLAUDE.md) · [runner](../runner/CLAUDE.md) ·
> [spotter](../spotter/CLAUDE.md) · [web](../web/CLAUDE.md) ·
> [server](../server/CLAUDE.md) · [bridge](../bridge/CLAUDE.md)),
> 검사도 `tests/<덩이>/` 로 나뉘었다. **이 문서는 「어느 파일」을 적고, 그 문서들은
> 「그 덩이에서 무엇이 값을 했는지」를 적는다.** 루트 `CLAUDE.md` 에는 권한과
> 덩이 경계, 그리고 어디서나 미는 함정만 남았다(587줄 → 136줄).

> **같은 지도가 볼 수 있는 페이지로도 있다** —
> <https://claude.ai/code/artifact/954ece81-76eb-4ca1-ad27-f1f954dbf0f5>
> 거기서는 일감마다 경로를 복사할 수 있다. **문구는 둘이 같아야 한다.**
> 숫자가 갈라졌는지는 `python scripts/map_numbers.py --check` 로 잰다.

숫자는 2026-09-18 실측이다.

## 1. 두 제품과 하나의 허브

세로는 제품이 둘이다 — **Study_EZ**(강의 한 편 → 예습·복습 덱)와 **땡시**(과목
하나 → 사진 문항 세트). **둘이 만나는 자리는 서버 하나뿐이다.**

```
  Study_EZ                              땡시 (Spotter)
  ──────────────────────────────        ──────────────────────────────
  quizgen/          12,373              spotter/scripts/     6,565
    퀴즈 생성. 강의록 PDF → 카드          재료 모으기 · 조합 · 배포
    모델이 쓴다
                                        spotter/web/         6,477
  runner/            8,376                화면. 기생충학 + 해부학 넷
    연결부. 파이프라인을 돌리고
    서버로 민다                          spotter-dist/        6,277
                                          배포 산출물
  web/src/          10,737                **손으로 고치지 마라**
    프론트. studyez.kr
  quizbank/            770
    Quiz Bank(2026-10-04). ChatGPT 응답 →
    정리·검증·외부지식 검토 → 쪽 PNG
  ──────────────────────────────        ──────────────────────────────
  ┌──────────────────────────────────────────────────────────────────┐
  │  server/app/      6,875   FastAPI · Cloud Run                    │
  │    두 제품이 만나는 유일한 자리. 계정·인증·R2 서명이 여기 하나다      │
  └──────────────────────────────────────────────────────────────────┘

  bridge/      1,814   예습링크 크롬 확장
                         (3,113 이었던 것은 `release/` 산출물이 섞여 있어서다.
                          .gitignore 가 옛 이름을 보고 있었다 — 2026-09-14 에 뗐다)
  platform/      228   둘이 정말 같이 쓰는 것 — session.js 하나
  tests/       9,120   748개. 덩이별로 나뉘어 있다 — 하나만 돌리면 된다
                         quizgen 405 · runner 317 · spotter 22 · bridge 4
                         `pytest tests` 19초  ·  `pytest tests/quizgen` 2초
  docs/                `archive/` 는 닫힌 기록이다
                       (줄수를 안 적는다 — 그 숫자를 적는 파일이 여기 있어서
                        적는 순간 틀린다)
```

## 2. 일감 → 읽을 곳

**왼쪽 일을 할 때 오른쪽만 주면 된다.** 나머지는 안 읽어도 된다.

**경로를 줄 때 그 덩이의 `CLAUDE.md` 는 저절로 실린다** — 따로 지목하지 않아도 된다.

| 하려는 일 | 주면 되는 경로 | 검사 |
|---|---|---|
| **사이트 화면**을 고친다 | `web/src/` + `web/src/types.ts` | `cd web && npm run typecheck` |
| ├ 캘린더 | `web/src/calendar/` (2,360줄) | |
| ├ 관리 화면 | `web/src/admin/` | |
| ├ 사람별 이용현황 | `web/src/admin/UsageTab.tsx` + `server/app/routes/usage.py` | `-m tests.test_usage` |
| ├ 예습 링크 열기 기록 | `server/app/routes/common.py`(`record_preview_open`) + `models.py` | `-m tests.test_usage` |
| ├ 문제 푸는 화면 | `web/src/lecture/` (1,330줄) | |
| ├ 복습 간격·되돌리기 | `server/app/srs.py` + `web/src/lecture/queue.ts` | `-m tests.test_srs` |
| ├ 색·여백 | `web/src/styles/` (3,622줄) | |
| ├ 덱 모아받기 | `web/src/bundle/` + `server/app/routes/bundles.py` | `-m tests.test_bundles` |
| ├ 덱 만드는 진행 | `web/src/calendar/DeckSlot.tsx` + `web/src/jobProgress.ts` + `server/app/routes/prequiz_jobs.py` | `-m tests.test_deck_watch` |
| └ 공지사항 · 이용방법 | `web/src/notices/` + `server/app/routes/notices.py` | `-m tests.test_notices` |
| **퀴즈 생성**을 바꾼다 | `quizgen/` + `tests/quizgen/` | `pytest tests/quizgen` (405개·2초) |
| ├ 카드를 어떻게 쓰는가 | `quizgen/prompts/` ← **여기가 대부분이다. §2-1** | `quizgen.judge` |
| ├ 단계 순서·재시도 | `quizgen/run.py` (662줄) | |
| ├ 기계 검증 규칙 | `quizgen/validate.py` (647줄) | |
| ├ 모델에게 풀려 보기 | `quizgen/reproduce.py` (755줄) | |
| └ 덱 굽기·뒷면 배치 | `quizgen/build.py` (1,119줄) | |
| **땡시 문항 오류**를 고친다 | `spotter/data/` + `spotter/scripts/build_web.py` | `pytest tests/spotter` (22개·7초) |
| **땡시 화면**을 고친다 | `spotter/web/` (기생충학) 또는 `spotter/web/anatomy/_template.html` (해부학) | |
| **서버 API**를 고친다 | `server/app/routes/<해당>.py` + `server/app/models.py` | `cd server && .venv/Scripts/python -m tests` |
| **덱이 안 만들어진다** | `runner/watch.py` · `runner/cycle.py` · `runner/agent.py` | `pytest tests/runner` (317개·15초) |
| **덱이 안 올라간다** | `runner/publish.py` · `runner/gate.py` | |
| **걸린 카드**를 사이트에서 고친다 | `web/src/cards/CardRow.tsx`(한 장) · `web/src/admin/CardReviewTab.tsx`(편을 가로질러) · `web/src/lecture/LectureCards.tsx`(강의 화면) + `server/app/routes/cards.py` | `-m tests.test_card_edits` |
| └ 고친 것이 덱(.apkg)에 가는 길 | `runner/site_edits.py` + `quizgen/site_edits.py` + `runner/rebuild.py` | `pytest tests/runner/test_site_edits_sync.py tests/quizgen/test_site_edits.py` |
| **예습 링크**가 안 붙는다 | `bridge/` + `server/app/preview_links.py` + `web/src/bridge/` | `pytest tests/bridge` (4개) |
| **Quiz Bank** — 만들기 버튼·풀이 창 | `web/src/bank/` (`BankPanel` · `BankStudy`) + `server/app/routes/bank.py` | `-m tests.test_bank` |
| ├ ChatGPT 에 가는 프롬프트 | `web/src/bank/bankPrompt.md` ← **정본. 머리 주석의 Version 을 올린다** | |
| ├ 정리·검증·외부지식 검토 | `quizbank/` (`organize` · `validate` · `review` · `slides`) | `pytest tests/quizbank` |
| ├ 다음 문항 고르기·숙련도 | `server/app/study_engine/` (`policy.json` 이 수치) | `-m tests.test_study_engine` |
| ├ 개념 지도 (학생) | `web/src/bank/ConceptMap.tsx` + `study_engine/engine.py`(`concept_map`) | `-m tests.test_study_engine` |
| ├ 러너가 받아 정리해 올리기 | `runner/bank.py` + `runner/agent.py`(`BANK`) | `pytest tests/runner/test_bank.py` |
| ├ 학생 「문제 있음」 보기 | `web/src/admin/BankReportTab.tsx` + `routes/bank.py`(`/bank-feedback`) | `-m tests.test_bank` |
| └ 확장이 답 본문을 가져오기 | `bridge/chatgpt-share.js`(`answerText`) + `bridge/background.js`(`STUDYEZ_BANK_ANSWER`) | `pytest tests/bridge` |

### 땡시 문항을 고칠 때 — 손으로 고치는 파일은 여섯뿐이다

`spotter/data/` 에 37개가 있는데 **대부분은 만들어지는 것**이다. 고칠 것은 이것들이다.

```
  question_corrections.json   족보 정답표가 틀렸을 때
  image_overrides.json        사진에 이름표가 잘못 붙었을 때
  species/*.json              종 마스터 (학명·감염경로·증상·치료…) — 군별 여섯 파일
  specimens/*.json            표본 마스터 (충란·성충·염색·배율…) — 네 파일
  glossary.json               용어 별칭
  identification_pairs.csv    사진으로 구별이 불가능한 짝
```

나머지(`generated_exams.json`·`coverage.csv`·`images.json`·`past_questions*.json`…)는
스크립트가 만든다. **거기를 고치면 다음 빌드에 덮인다.** `species.csv`·`specimens.csv`
도 `build_master.py` 가 위 두 폴더에서 써 내는 엑셀 검토용이다.

고친 뒤 도는 순서:

```bash
python spotter/scripts/build_master.py     # species/·specimens/ → .json + .csv
python spotter/scripts/build_web.py        # → build/quiz_db.json
python spotter/scripts/upload_web.py       # → R2
```

## 2-1. `quizgen/prompts/` 안쪽 — 카드 문구를 바꿀 때

**여기가 「퀴즈 생성을 바꾼다」의 대부분이다.** 파이썬을 안 고치고 이 폴더만 고치는
일이 흔하다. 다만 **두 종류가 섞여 있고 읽는 방식이 다르다.**

### ① 조립되는 모듈 — `prompting.py` 가 합쳐서 한 장으로 만든다

    CORE (항상, 넷)              PROFILE (하나)          ADAPTERS (자료에 따라)      DOMAIN (하나)
    core/quality.md    242줄     profiles/               adapters/                  domains/
      무엇이 좋은 카드인가         exam_review.md   13      lecture_pdf.md    16        medical_ko.md  95
    core/evidence.md    21         시험 복습용            annotations.md     8           한국어 의학
      근거는 자료에 있어야        prelecture.md    14      past_exam.md      21        generic.md      4
    core/media.md       35         수업 전 예습           medical_past_exam 13           분야 없음
      표·그림을 어떻게 읽나
    core/language.md    20
      질문 문체

순서가 저 순서다(`prompting.module_names`). **한 파일만 고치면 모든 편에 실린다** —
`core/` 가 특히 그렇다. 분야에 매인 말은 `domains/` 로 내려야 한다.

| 바꾸고 싶은 것 | 고칠 파일 |
|---|---|
| 좋은 카드의 기준, 형식 비율, 금지 | `core/quality.md` ← **제일 자주 고치는 곳** |
| 근거 없는 카드를 막는 규칙 | `core/evidence.md` |
| 표·그림·이미지 카드 | `core/media.md` |
| 질문 말투 | `core/language.md` |
| 복습 덱만 / 예습 덱만 | `profiles/exam_review.md` / `profiles/prelecture.md` |
| 의학 용어·번역어·실제 카드 예시 | `domains/medical_ko.md` |
| 기출을 어떻게 쓰는가 | `adapters/past_exam.md` |

### ② 단계별 과제문 — 코드가 그때그때 직접 읽는다

    plan.md              41   ① 무엇을 낼지 계획한다            assemble.py
    cards.md             67   ② 계획대로 카드를 쓴다             assemble.py
    revise.md            83   판이 갈린 슬라이드만 갈아 끼운다     revise.py
    reproduce_answer.md  24   질문만 주고 다시 풀린다             reproduce.py
    reproduce_grade.md   40   원래 답과 같은지 채점한다           reproduce.py
    reproduce_axis.md    28   빈칸이 무엇을 묻는지 대게 한다       reproduce.py
    repair.md            50   검사에 걸린 카드를 고쳐 쓴다         run.py
    repair_leak.md       14   앞면에 답이 샌 것을 고친다           run.py
    judge_cloze.md       38   두 판의 cloze 를 가려 놓고 판정한다   judge.py
    philosophy.md        10   **지금은 안 쓴다.** 조립으로 옮겨 갔다는 안내만 남았다

예습은 자기 것을 따로 든다 — `quizgen/prequiz/prompts/` 에 `must.md`(꼭 알아야 할
것 고르기) · `cards.md` · `repair.md` 셋. `core/`·`domains/` 는 같이 쓴다.

### ③ 여기서 조심할 것 둘

**예시로 쓴 편으로는 그 규칙을 재지 마라.** `domains/medical_ko.md` 의 「실제 카드」
예시가 어느 편에서 왔는지는 `quizgen/prompting.py` 의 `DOMAINS` 위 주석에 있다.
2026-09-05 에 코어 예시가 한 편에 몰려 있었고, 그 편을 돌려 보니 **cloze 14장 중
5장이 예시에서 그대로 나왔다.** 「규칙이 작동했다」로 읽을 뻔했다. 주제까지 봐야
한다 — 작년 말라리아 예시는 올해 말라리아 편에도 닿는다.

**문구가 나은지는 파이프라인 실행으로 재지 마라.** 같은 편 같은 자료인데 판마다
cloze 6~16장 · 재현 78~91% 로 흔들린다. 만들려던 효과가 그 폭에 묻힌다.

    python -m quizgen.judge cloze out/exp_A out/exp_B    30초 · $0.35

이미 만들어 둔 카드를 판마다 뽑아 섞고 **한 세션에게** 가린 채 판정시킨다.
근거는 `CLAUDE.md` 의 「프롬프트를 고치고 한 편 돌려서 비교하지 마라」 절에 있다.

## 3. 연결부 — 덩이끼리 닿는 자리는 넷뿐이다

**이것이 「전체를 안 읽어도 되는」 이유다.**

### ① 파이썬 import — 딱 한 파일

    runner/deck.py  →  quizgen  (3줄)

전부다. `server/app` 은 `quizgen`·`runner` 를 **하나도 import 하지 않고**, `spotter`
도 마찬가지다. 나머지 연결은 전부 하위 프로세스(`python -m quizgen.run`)로 간다.

**Quiz Bank(2026-10-04)도 이 선을 안 넘는다.** 러너는 `quizbank` 를 import 하지 않고
`python -m quizbank.run` 으로, 족보 조각 판정은 `python -m quizgen.slicefor` 로 부른다.
`quizbank` 도 `quizgen` 을 import 하지 않는다 — 눈먼 `claude -p` 30줄을 따로 둔 이유다.

### ② HTTP — 전부 서버를 향한다

    runner/          → 서버 경로 9개    (/api/admin/lectures · prequiz-jobs · local-storage)
    web/src/         → 서버 경로 23개
    spotter/scripts/ → 서버 경로 10개   (/api/spotter/admin/…)
    bridge/          → 서버 경로 2개

**가로로는 아무도 서로를 안 부른다.** 프론트가 러너를 부르지 않고 땡시가
quizgen 을 부르지 않는다. 그래서 서버 계약(`openapi`)만 안 바뀌면 한쪽만 고쳐도 된다.

계약을 지키는 자: `server/tests/test_route_contract.py` — 경로 70줄이 그대로인지 본다.

### ③ 파일 — `runs/<편>/` 이 quizgen 과 runner 사이의 계약이다

```
  prep.json              quizgen.prep 이 만든다 · runner.fingerprint 가 읽는다
  items.raw.json         ② 모델이 쓴 카드
  items.checked.json     기계 검증 통과분
  items.reproduced.json  모델에게 풀려 본 결과
  run.meta.json          runner.deck.contract 가 만든다 · 서버와 문지기가 읽는다
  *.apkg                 덱
```

칸 이름과 뜻은 [artifact-contract.md](artifact-contract.md) 와 [runs-layout.md](runs-layout.md) 에 있다.

### ④ 공유 파일 — 하나

    platform/session/session.js
      → web/src/supabase.ts   import 한다
      → spotter/web/session.js  사본 (`spotter/scripts/sync_shared.py --check` 가 지킨다)

## 4. 안 겹치는 것 — 읽을 필요가 없다

- **풀이 화면 둘은 다른 제품이다.** Study_EZ 는 자기채점 자유회상, 땡시는 시간
  재는 다지선다. 한쪽을 고칠 때 다른 쪽을 볼 일이 없다
- **`quizgen/prequiz/` 는 `quizgen/` 의 복제가 아니다.** `..build`·`..pack`·
  `..validate` 를 import 한다 — 이미 나뉘어 있다
- **`spotter-dist/` 는 산출물이다.** `spotter/` 를 고치고 `spotter/scripts/deploy_pages.py` 를 돌린다
- **`docs/archive/` 는 닫힌 기록이다.** 현재 상태로 읽지 마라

## 5. 이 문서를 안 믿어야 할 때

숫자는 실측이고 **줄수는 금방 낡는다.** 낡았는지는 한 명령으로 잰다.

```bash
python scripts/map_numbers.py            # 실측과 지도를 나란히
python scripts/map_numbers.py --check    # 다른 줄만 찍고 1로 끝난다
```

**줄수가 낡는 것은 괜찮다.** 중요한 것은 **경계**(§3)이고, 같은 도구가 그것도 센다 —
경계를 넘는 파이썬 import 가 **0 이 아니면 2로 끝난다.**

    경계 넘는 import  0   ← 이 줄이 0 이 아니면

**그때는 이 지도가 아니라 구조가 틀린 것이다.** 그 import 를 없앨 수 있는지 먼저 본다.

같은 도구가 **문맥이 다시 모이는지도** 센다. 셋을 본다.

    검사를 덩이별로       tests/<덩이> 가 비면 옮기다 흘린 것이다
    덩이 문서            <덩이>/CLAUDE.md 가 없으면 루트를 통째로 읽게 된다
    루트 CLAUDE.md 줄수   **덩이 하나의 것을 루트에 적으면 이 숫자만 늘어난다**

셋째가 이 갈라 놓기가 되돌아가는 자리다. 2026-09-14 에 136줄에서 시작했다.

서버 경로가 그대로인지는 따로 본다.

```bash
cd server && .venv/Scripts/python.exe -m tests.test_route_contract
```

## 6. 이 지도는 두 곳에 있다

저장소의 이 파일이 정본이고, 관리자가 보는
[Artifact 페이지](https://claude.ai/code/artifact/954ece81-76eb-4ca1-ad27-f1f954dbf0f5)가
같은 내용을 낸다. **2026-09-14 에 벌써 갈라졌다** — 검사 수가 한쪽은 604, 다른 쪽은
606이었다. 손으로 맞추면 또 갈라지므로 `scripts/map_numbers.py` 를 만들었다.

한쪽을 고치면 **다른 쪽도 같이 고친다.** 페이지는 같은 파일 경로로 다시 내면
같은 주소에 덮인다.

## 7. 옆 문서 둘

이 문서는 **어디를 보는가**만 적는다. 나머지 둘이 그 앞뒤를 든다.

| 문서 | 무엇을 적나 | 언제 보나 |
|---|---|---|
| [layout.md](layout.md) | **왜 지금 모양인가.** 무엇이 무엇으로 개명됐는지, 옛 이름을 어디에 남겨 뒀는지, 배포 셋이 각각 어떻게 나가는지 | 옛 이름으로 적힌 문서·커밋을 만났을 때. 배포할 때 |
| [refactor-plan.md](refactor-plan.md) | **무엇을 합치려 했고 무엇을 안 합쳤는가.** Phase 별 판정과 그 근거가 된 실측 표 | 「이건 왜 아직 둘이지?」 싶을 때 |

**셋이 어긋나면 이 문서가 맞다** — 여기 숫자만 `scripts/map_numbers.py` 가 잰다.
`refactor-plan.md` §0 아래는 **09-12 의 기록**이고 다시 재지 않았다(그 문서가 스스로 적고 있다).
