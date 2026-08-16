---
name: quiz
description: 강의 PDF와 그 안의 족보(기출)에서 의대 시험 대비 Anki 카드를 만들어 슬라이드 이미지가 붙은 .apkg까지 뽑는다. 사용자가 /quiz를 부르거나, 특정 강의 PDF로 카드·문제·Anki 덱을 만들어 달라고 할 때 사용한다.
---

# 강의 PDF → 시험 대비 Anki 덱

강의 한 편을 받아 **Opus 5 호출 3+N회**와 코드 4패스로 Anki 덱을 만든다.
0.5·1·4단계가 각 1회이고, 2단계는 주제 조각 수만큼(보통 4~6) 동시에 돈다.
실측(강의록 25쪽·75장): 0.5단계 3분 · 1단계 14분 · 2단계 8분(조각 6개 병렬) ·
4단계 21분 · 코드 2분 = **약 48분.** 조각을 병렬로 돌려도 1·4단계가 길어 전체는
크게 안 줄어든다 - 조각화가 줄이는 것은 시간이 아니라 **한 번에 죽을 위험**이다.
모델은 카드와 **슬라이드 번호**까지만 책임진다. 이미지 첨부와 패키징은 코드가 한다.

목적과 출제 규칙은 [references/item-rules.md](references/item-rules.md)에 있다.
**이 파일은 절차만 다룬다. 무엇을 어떻게 출제할지는 전부 그쪽이다.**

## 역할 경계 (어기지 말 것)

| | 코드 (`quiz/`) | 모델 (이 스킬) |
|---|---|---|
| 하는 일 | PDF 자르기·각인·렌더, 족보 구간 분리, 스키마·범위·중복 검사, 덱 패키징 | 무엇을 물을지, 어떻게 물을지, 무엇을 지울지 |
| 안 하는 일 | 의미 판단 일절 | 파일명·이미지·ID 조작 일절 |

## 실행 절차

인자로 받은 강의 PDF 경로를 `<pdf>`라 한다. 인자가 없으면 아래에서 목록을 보여주고 묻는다.

    ~/SynologyDrive/{과목}/필기/{연도}/[YYMMDD_NN]제목(교수)_필기자vN.pdf

Main-Quiz는 **올해** 필기가 대상이다. 어느 강의의 작년 판인지는
`python -m studyez match {과목}`이 알려준다.

아래 `python`은 이 환경에서 PATH에 없다. 실제로는
`PYTHONIOENCODING=utf-8 "C:/Users/ows01/anaconda3/python.exe"` 로 부르고,
작업 디렉터리는 이 저장소 루트다.

### 0단계 — 준비 (코드)

```bash
python quiz/prep.py "<pdf>"
```

`runs/<lecture_id>/`에 생기는 것:

- `model_pages/clean_sNNN.png` — **전 페이지.** 필기 제거 + `Slide N` 각인. 사실을 읽는 채널
- `jokbo_pages/jokbo_sNNN.png` — **뒤 절반.** 필기 포함(문항이 annotation에만 있을 수 있음) + `Slide N` 각인
- `page_features.json` — 페이지별 글자수·annotation 수·답안 나열·족보 낱말·이미지 비율·**붙여넣은 이미지 수**. 0.5단계 입력
- `jokbo_text.md` — `--jokbo-pdf`를 줬을 때만. **원본 족보의 원문 텍스트.**
  선지를 한 글자도 흘리지 않고 옮길 수 있어 이쪽을 먼저 읽는다. 다만 정답표와
  사진 문항은 이미지에만 있으므로 `jokbo_pages/`를 함께 봐야 한다
- `outline.json` / `annotations.json` — 슬라이드별 본문 요약, 필기·형광펜·**도장(stamp)** 신호
- `labels.json` — 슬라이드별 라벨 후보와 정확한 bbox. 이미지 오클루전 카드가 여기서 좌표를 가져온다
- `media/` — Anki 카드 뒷면용 슬라이드 PNG
- `prep.json` — `jokbo_hint`, `slide_image_map` 등 계약 파일

**두 채널이 겹쳐서 렌더된다.** clean은 전 페이지, annotated는 뒤 절반이다. 경계가 어디로
정해지든 다시 렌더하지 않게 하려는 것이다. `prep.json`의 `jokbo_hint`는 **힌트일 뿐이고
경계의 주인은 0.5단계다.** 출력에서 stamp가 찍힌 슬라이드와 "라벨 많은 슬라이드"를 본다 —
뒤쪽은 그림 슬라이드 후보이고, 오클루전 카드를 낼 자리를 여기서 미리 본다.

**색은 나오지 않는다.** 필기자마다 도구도 규약도 달라 같은 색이 정반대를 뜻한다.
회색이 사담일 때도 있고 "이 부분은 시험에 안 낸다고 하셨습니다" 같은 결정적인 말일
때도 있다. 뜻은 색이 아니라 **글에 있다** — `annotations.json`의 `notes`를 읽어라.
거기에 필기자가 적어 둔 말이 그대로 있고, 그게 어떤 색보다 확실한 신호다.

**서브에이전트에게 채널을 명시하라.** 이 환경에는 poppler가 없어 Read 툴이 PDF 페이지를
렌더하지 못한다. 채널을 지정하지 않으면 에이전트가 필기가 살아 있는 `media/`로 우회하고,
강의록 구간의 사실/신호 분리가 조용히 무너진다.

### 0.5단계 — 구조 판별 (Opus 5 호출 ⓪)

`general-purpose` 서브에이전트. **문항도 카드도 만들지 않는다.** 경계와 주제만 정한다.

족보 경계는 문구 정규식으로 못 잡는다. 실물에서 이렇게 깨졌다 — 표지가 "정답"이면
낱말 목록에 없어서 놓치고, 문항 본문이 annotation 이미지뿐이면 "빈 페이지" 폴백도 안
걸린다. 필기자마다 쓰는 말이 다르고 앞으로도 다를 것이라, 규칙을 늘리는 대신 판단을 넘긴다.

> `runs/<lecture_id>/page_features.json`과 `outline.json`을 읽어라. 그다음
> `jokbo_pages/jokbo_sNNN.png`를 **전부** 읽어라. 강의록 뒷부분과 족보가 섞여 있고,
> 어디서 갈리는지를 네가 정한다.
>
> 판정을 `runs/<lecture_id>/structure.json`에 쓴다.
>
> - `lecture_range` `[1, N]` — 강의록 구간
> - `jokbo_range` `[N+1, 끝]` 또는 `null` — 기출 구간. 강의록과 겹치지 않고 사이가 비지 않게
> - `jokbo_evidence` — 왜 거기서 갈리는지 한 줄. 슬라이드 번호를 대라
> - `chunks` — 강의록의 **주제 덩어리**. `{id, title, slides: [시작, 끝], summary}`.
>   `lecture_range`를 **빠짐없이·겹침없이** 덮어야 한다. 한 덩어리는 대략 5~15장이다
>
> 슬라이드 번호는 세지 말고 **각인된 노란 `Slide N` 라벨을 읽어서** 적어라.
> 헷갈리면 `jokbo_range`를 넓게 잡지 말고 좁게 잡아라 — 강의록을 족보로 오인하면
> clean 채널을 잃고 사실 근거가 통째로 사라진다.

```bash
python quiz/structure.py runs/<lecture_id>
```

경계가 자료의 모양과 맞는지 기계가 따진다. 답안표가 족보 구간에 있는지, 족보 구간에
강의록 수준의 본문이 섞였는지, chunk가 구간을 다 덮는지를 본다. **불평이 하나라도 나오면
그 단계를 다시 시킨다.** 손으로 JSON을 고쳐 넘기지 마라 — 여기서 잘못되면 뒤가 전부
어긋난다.

#### 족보가 없다고 나왔을 때만 작년을 끌어온다

```bash
python -m studyez prep-prev <lecture_id>
```

`jokbo_range`가 `null`일 때만 실제로 작업한다. 있으면 아무것도 안 하고 끝난다 —
**필기자가 작년 족보를 그대로 옮겨 오기 때문에, 올해 필기에 족보가 붙어 있으면
작년 것은 그 부분집합이다.** 실측으로 확인했다(`260812_01`: 작년 18문항이 올해
족보에 100% 포함).

작년을 끌어왔다면 그 run에도 0.5단계를 한 번 더 돌려 족보 구간을 잡은 뒤,
1단계에서 두 곳의 `jokbo_pages/`를 모두 읽어라.

### 1단계 — 청사진 (Opus 5 호출 ①)

`general-purpose` 서브에이전트. **카드는 만들지 않는다.** 무엇을 물을지만 정한다.

`structure.json`의 `lecture_range`·`jokbo_range`가 이 단계의 범위다. `chunks`는 이미
나뉜 주제이므로 다시 나누지 말고 그 위에 목표를 얹어라.

> `runs/<lecture_id>/structure.json`을 먼저 읽어 구간과 주제를 확인하라.
> `jokbo_range`가 있으면 `jokbo_pages/`의 그 범위를 **먼저** 전부 읽어라. 교수가 무엇을
> 어떻게 묻는지가 거기 있다. 그다음 `model_pages/clean_sNNN.png`를 강의록 범위만큼 전부 읽고,
> `outline.json`과 `annotations.json`도 읽어라.
>
> `.claude/skills/quiz/references/item-rules.md`를 **전부** 읽어라. 특히 §1(무엇을
> 카드로 만드는가), §3(중요도와 출제 이력), §4(족보).
> 청사진을 `runs/<lecture_id>/blueprint.json`에 쓴다. 스키마는 `references/blueprint.schema.json`.
>
> - 족보에서 읽어낸 출제 성향을 `exam_focus`에 남겨라
> - 각 `retrieval_target`에 `study_tags`(important / frequent / detail)를 붙여라
> - 제외는 §1의 여섯 사유 중 하나에 해당할 때만이다
> - `annotations.json`의 `stamp`는 기출 출제 이력이므로 `frequent`의 근거가 된다
> - 족보가 그림으로 묻거나, 위치와 이름의 대응이 시험 대상인 슬라이드는 §15를 읽고
>   이미지 오클루전 대상으로 표시하라

받은 뒤 직접 `blueprint.json`을 열어 세 태그가 모두 나타나는지, 강의록 슬라이드가
빠짐없이 다뤄졌는지 확인한다.

### 2단계 — 카드 작성 (Opus 5 호출 ②, **조각별 동시 실행**)

**한 번에 다 쓰게 하지 마라.** 76장을 한 호출에 맡겼더니 `260812_02`에서 **68분을
돌다 API 오류로 죽었고 아무것도 남기지 못했다.** 기준 강의의 19분과 견주면 3.5배다.

`structure.json`의 `chunks`가 이미 주제 경계를 들고 있다. 청사진의 objective를
그 경계로 나눠 **조각마다 서브에이전트를 하나씩, 동시에** 돌린다. 족보는 별도
조각이다.

    c1     obj_1~3     슬라이드 1-6      →  items.raw.c1.json
    c2     obj_4~6     슬라이드 7-11     →  items.raw.c2.json
    ...
    jokbo  obj_14~19   슬라이드 26-39    →  items.raw.jokbo.json

조각 하나는 5분 안팎이고 서로 독립이라 **하나가 죽어도 나머지는 남는다.**
objective를 조각에 배분할 때는 `slides`의 최솟값이 어느 chunk 범위에 드는지로
가린다.

각 조각에 **그 대목의 급소를 따로 일러줘라.** 청사진의 `exam_focus`와
`trap_patterns`에서 해당 슬라이드에 걸리는 것을 뽑아 넘기면 카드가 눈에 띄게
날카로워진다.

```bash
python quiz/merge_items.py runs/<lecture_id>
```

조각을 `items.raw.json` 하나로 합치고 `id`를 다시 매긴다 — 조각들은 서로를 몰라
그대로 두면 `q001`이 여러 개 생긴다. 조각이 같은 슬라이드를 나눠 가졌으면
중복 의심으로 알리고, 판단은 4단계에 맡긴다.

각 조각에 주는 지시는 아래와 같다. `<조각>`과 objective 목록만 갈아 끼운다.

> `blueprint.json`의 **`obj_N`~`obj_M`만** 만든다. 다른 objective는 다른
> 에이전트 몫이니 손대지 마라.
> 강의록은 `model_pages/`를, 족보는 `jokbo_pages/`와 `jokbo_text.md`를 읽어라.
> `references/item-rules.md`를 **전부** 읽고 그 규칙대로 카드를 만든다.
> 결과를 `runs/<lecture_id>/items.raw.<조각>.json`에.
> 스키마는 `references/item.schema.json`. `id`는 `<조각>_001`처럼 매긴다.
>
> - 모든 카드는 청사진의 `objective_id`와 `retrieval_target`에 묶인다
> - `slide_no`는 페이지를 세지 말고 **각인된 노란 `Slide N` 라벨을 읽어서** 적는다
> - 강의록 카드는 `source_type: "lecture"`, 족보 카드는 `"jokbo"`
> - 족보 카드는 선지에 의존하지 않게 자족적으로 압축한다 (§4.2)
> - 족보 정답이 검토 결과와 다르면 `review_flags`와 `review_note`를 남긴다 (§4.4)
> - 답은 핵심만, 부연은 `explanation`으로 (§11). 해설은 자료 밖 지식을 써도 된다 (§12)
> - 무엇과 헷갈리는지는 `trap_note`에 한 줄로. `trap` 유형은 필수다 (§12)
> - 그림 카드는 `labels.json`에서 `label_ids`를 골라 `occlusion`에 적는다. 좌표를 눈대중으로 찍지 마라 (§15)
> - 청사진의 target 중 카드를 만들지 않은 것은 `skipped`에 사유와 함께 남긴다

### 3단계 — 기계 검증 (코드)

```bash
python quiz/validate.py runs/<lecture_id>
```

`items.checked.json`(빌드 가능)과 `suspects.json`(감사 대상)이 나온다.
출력의 카드 수·난이도 분포·출처 분포를 사용자에게 한 줄로 보고한다.

### 4단계 — 감사 (Opus 5 호출 ③)

새 `general-purpose` 서브에이전트. **카드를 쓴 에이전트를 재사용하지 마라.**

**최종 배열을 통째로 쓰게 하지 마라.** 74장을 다시 출력하면 2단계가 죽었던 그
자리에 또 걸린다. 감사가 실제로 손대는 것은 보통 2~3할이니 **바뀐 것만** 쓰게 한다.

조각을 나눠 돌렸으면 **조각 경계에서 중복이 났는지 반드시 확인시켜라.**
`merge_items.py`가 같은 슬라이드를 나눠 가진 곳을 짚어 준다. 기계는 회상 목적이
같은지까지는 못 본다.

> `suspects.json`과 `items.checked.json`을 읽어라. 원본 확인이 필요하면 강의록은
> `model_pages/`, 족보는 `jokbo_pages/`(또는 `jokbo_text.md`)에서 해당 슬라이드만 읽어라.
> `references/item-rules.md`의 **§16 감사 기준**을 따른다.
> **패치만** `runs/<lecture_id>/audit_patch.json`에, 판정 근거를 `audit.md`에 쓴다.
>
> ```json
> { "edit": [ { "id": "q012", "a": "고친 답" } ],
>   "drop": [ { "id": "q034", "reason": "q031과 회상 목적이 같다" } ],
>   "add":  [ { ...스키마를 갖춘 새 카드... } ] }
> ```
>
> `edit`은 **바꿀 필드만** 적는다. 언급하지 않은 카드는 자동으로 유지된다.
> `id`는 못 바꾼다 — 틀렸으면 `drop`하고 새로 `add`하라.
>
> - `flagged` — 수정 / 유지 / 삭제 중 하나
> - `answer_too_long`·`compound_question` — 부연을 `explanation`으로 옮기거나 카드를 쪼개면 대부분 해결된다
> - `near_duplicate_groups` — 회상 목적이 같은 것만 줄인다. 족보 카드와 강의록 카드가 같은 것을 물어도 목적이 달라 둘 다 남긴다
> - `detail_not_exclusive` — `detail`은 단독으로만 붙는다. 실제로 중요하거나 출제되는 내용이면 `detail`을 떼라
> - `removed` — `slide_no`만 틀린 것은 원본에서 번호를 확인한 뒤 되살려라
> - `coverage_gaps` — 해당 슬라이드를 다시 읽고 만들 수 있으면 만든다
> - `untouched_slides` — 통째로 빠진 슬라이드가 §1의 제외 사유에 해당하는지 직접 확인하라
> - `study_tags` — 세 태그 중 어느 것도 비어 있으면 안 된다
> - `occlusion`이 붙은 카드는 그 슬라이드를 직접 열어 **무엇이 가려졌는지** 확인하라.
>   기계는 라벨 id가 실재하는지까지만 본다 (§16)
> - `no_trap_note` — `trap` 유형인데 함정이 비었다. 채우거나 유형을 바꿔라

### 5단계 — 빌드 (코드)

```bash
python quiz/apply_audit.py runs/<lecture_id>          # 패치 → items.final.json
python quiz/validate.py runs/<lecture_id> --items items.final.json   # 다시 통과하는지
python quiz/build.py runs/<lecture_id> --items items.final.json --project <과목>
```

감사 패치를 반영한 뒤 **검증을 한 번 더 돌린다.** 고친 것이 정말 고쳐졌는지는
기계가 세어야 안다 — 실측에서 soft 22건이 1건으로 떨어지는 것을 여기서 확인했다.

`slide_no`가 범위를 벗어나거나 이미지가 없으면 **빌드가 중단된다.** 임의로 번호를 바꾸지 말고
4단계로 되돌려 원본에서 확인시켜라. 오클루전 좌표가 풀리지 않을 때도 마찬가지다.

빌드는 마지막에 쓴 `.apkg`를 도로 열어 노트·카드·미디어 수를 실제로 센다.
여기서 실패하면 덱이 깨진 것이므로 **사용자에게 넘기지 마라.**
`runs/INDEX.md`(빌드한 덱 대장)도 이때 갱신된다.

## 사용자 보고

- 덱 이름, 카드 수, 학습 단계(important/frequent/detail)·출처(강의록/족보) 분포
- 이미지 오클루전 카드 수
- 족보 정오 검토 플래그가 붙은 카드 수
- 감사에서 삭제/수정/보충한 수
- **카드가 하나도 없는 슬라이드 번호** — 사용자가 직접 확인해야 할 항목
- `.apkg` 경로. Anki에서 수동 import한다 (자동 투입하지 않는다)

## 실패 시

- 서브에이전트가 스키마를 어긴 JSON을 쓰면 그 단계만 다시 시킨다. 손으로 JSON을 고쳐 넘기지 않는다
- `validate.py`가 대량으로 hard 제거하면 2단계 지시가 잘못됐다는 신호다. 감사로 덮지 말고 2단계를 다시 돌린다
- 족보 구간을 잘못 잡으면 `prep.py --jokbo-start N`부터 다시
- 사용자가 카드 품질을 지적하면 `references/item-rules.md`의 해당 절을 직접 고친다. 다음 실행부터 세 에이전트가 그 규칙을 읽는다
