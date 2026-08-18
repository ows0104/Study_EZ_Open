---
name: prequiz
description: 강의 PDF에서 강의 직전에 푸는 예습확인퀴즈(객관식·단답·OX)를 만들어 슬라이드 이미지가 붙은 .apkg까지 뽑는다. 사용자가 /prequiz를 부르거나, 특정 강의 PDF로 예습 문제·예습 점검 퀴즈를 만들어 달라고 할 때 사용한다. 시험 대비 반복 암기 카드가 필요하면 quiz 스킬을 쓴다.
---

# 강의 PDF → 예습확인퀴즈 덱

강의 한 편을 받아 **Opus 5 호출 4회**(0.5·1·2·4단계)와 코드 3패스로
예습확인퀴즈를 만든다. 실측 약 34분.
학생이 강의 직전 5~10분에 풀고, **틀린 문항이 그 강의의 청취 목표가 된다.**

출제 규칙은 [references/preview-rules.md](references/preview-rules.md)에 있다.
**이 파일은 절차만 다룬다. 무엇을 어떻게 물을지는 전부 그쪽이다.**

## `quiz` 스킬과의 관계

| | `quiz` | `prequiz` (여기) |
|---|---|---|
| 목적 함수 | 시험 점수 | 그날 강의를 따라가기 |
| 언제 | 강의 후, 시험 대비 반복 | 강의 직전 1회 점검 |
| 분량 | 슬라이드당 여러 장 | 정보량대로. **20문항 이하** |
| 형식 | 앞·뒤 회상 카드, cloze | 객관식 5지선다 / 단답 / OX |
| 족보 | 문항으로 출제 | 우선순위 판단에 쓰고, **강의의 중심 흐름 위에 있을 때만** 출제 |
| 산출 | `<강의>.apkg` | `<강의>_예습.apkg` (하위 덱 `::예습확인`) |

같은 `runs/<lecture_id>/`를 공유하되 파일 이름이 `pre_`로 갈린다. 서로 덮어쓰지 않는다.

## 역할 경계 (어기지 말 것)

| | 코드 (`quiz/prep.py`, `prequiz/`) | 모델 (이 스킬) |
|---|---|---|
| 하는 일 | PDF 자르기·각인·렌더, 족보 구간 분리, 선지 번호 부여, 스키마·범위·중복·선지 검사, 덱 패키징 | 무엇을 물을지, 어떻게 물을지, 무엇을 버릴지 |
| 안 하는 일 | 의미 판정 (세어서 표시만 한다) | 파일명·이미지·ID·선지 번호 조작 |

선지 번호 ①②③④⑤는 **코드가 붙인다.** 모델은 선지 본문과 정답 인덱스까지만 적는다.

## 실행 절차

인자로 받은 강의 PDF 경로를 `<pdf>`라 한다. 인자가 없으면 아래에서 목록을 보여주고 묻는다.

    ~/SynologyDrive/{과목}/필기/{연도}/[YYMMDD_NN]제목(교수)_필기자vN.pdf

Pre-Quiz는 **작년** 필기가 대상이다. 족보가 정리돼 붙어 있는 쪽이 작년이다.
올해 강의에 대응하는 작년 파일은 `python -m studyez match {과목}`이 알려준다.

#### 인자가 없을 때 먼저 보는 곳

```bash
python -m studyez prequeue
```

관리자가 `/admin`에서 저장한 예습 링크를 받아 **작년 짝을 고르고, 0단계를 돌리고,
공유 대화를 `runs/<작년 run_id>/preview.md`로 앉힌 뒤** `runs/prequeue.json`에 적는다.
`state`가 `ready`(아직 안 만듦)나 `stale`(다른 대화로 만든 덱이 있음)인 것이 할 일이고,
각 항목의 `prev_pdf`가 이 스킬의 `<pdf>`다. `state`가 `done`이면 이미 만든 편이다.

이미 `preview.md`가 앉아 있으므로 **0단계를 다시 돌리지 않는다.** 0.5단계부터 간다.

아래 `python`은 이 환경에서 PATH에 없다. 실제로는 `PYTHONIOENCODING=utf-8
"C:/Users/ows01/anaconda3/python.exe"` 로 부르고, 작업 디렉터리는 이 저장소 루트다.

### 단계마다 시각을 찍는다

```bash
python quiz/timings.py runs/<lecture_id> start 1-blueprint
python quiz/timings.py runs/<lecture_id> end   1-blueprint
python quiz/timings.py runs/<lecture_id> report
```

**코드 단계는 스스로 찍는다** — `prep.py`·`structure.py`·`prequiz/validate.py`·
`prequiz/build.py`가 자기 구간을 남긴다. 아무것도 안 해도 된다.

**모델 단계는 네가 찍는다.** 서브에이전트를 띄우기 직전에 `start`, 받은 직후에 `end`.
`0.5-model` · `1-blueprint` · `2-write` · `4-audit` 넷이다.

**왜 찍나.** 편당 34분을 어디서 줄일지 정하려면 단계별 소요가 있어야 하는데,
Pre-Quiz에는 그 값이 **아직 하나도 없다.** 2026-08-18 무인 실행에서 총 37.4분이
나왔지만 그 안이 통짜였고, 2단계가 병목이라는 것도 토큰으로 추정한 것이지
(캐시 읽기 9.5M) 시간을 잰 것이 아니다.

`quiz` 쪽에서는 이 계측이 실제로 코드를 바꿨다 — `plan_chunks.py`의 회귀 계수가
전부 여기 구간에서 나왔고 편당 6.8분을 줄였다. 그쪽도 완전 분해가 둘뿐이다.
**한 편은 분포가 아니다. 쌓일 때까지 계속 찍어라.**

재기만 한다. 느리다/빠르다는 판정은 사람이 한다.

### 0단계 — 준비 (코드)

```bash
python quiz/prep.py "<pdf>"
```

`quiz` 스킬과 **같은 스크립트, 같은 출력**이다. `runs/<lecture_id>/prep.json`이 이미 있고
같은 PDF에서 나온 것이면 다시 돌리지 않아도 된다.

`runs/<lecture_id>/`에 생기는 것:

- `model_input.pdf` — **출제의 본체.** 필기 제거 + `Slide N` 각인. 슬라이드 N = **N쪽**
- `annotated.pdf` — **족보 채널.** 원본 그대로 + 각인. 우선순위 판단용이자, 중심 흐름일 때는 출제 대상. 슬라이드 N = **N쪽**
- `jokbo_input.pdf` — `--jokbo-pdf`를 줬을 때만. 원본 족보 + 각인.
  **여기만 offset이 붙는다** — 슬라이드 N = (N − `prep.json`의 `jokbo_slide_offset`)쪽
- `page_features.json` — 페이지별 글자수·annotation·답안 나열·족보 낱말·**붙여넣은 이미지 수**. 0.5단계 입력
- `jokbo_text.md` — `--jokbo-pdf`를 줬을 때만. 원본 족보의 원문 텍스트
- `outline.json` / `annotations.json` — 슬라이드별 본문 요약, 필기·형광펜·**도장(stamp)** 신호
- `media/` — Anki 카드 뒷면용 슬라이드 PNG. **모델 입력이 아니다**
- `prep.json` — `jokbo_hint`, `slide_image_map` 등 계약 파일

`prep.json`의 **`poppler_available`이 `false`면 `pages` 읽기가 안 된다.** prep은 그래도
성공하므로 2단계에 가서야 터진다. 0단계 출력의 경고를 보고, 뜨면 앱을 완전히 종료했다 켜라.

**두 채널이 겹쳐서 나온다.** 둘 다 전 페이지이고 쪽 번호도 같다. 경계가 어디로
정해지든 다시 만들지 않게 하려는 것이다. `prep.json`의 `jokbo_hint`는
**힌트일 뿐이고 경계의 주인은 0.5단계다.**

#### PDF를 읽는 법

```
Read( runs/<lecture_id>/model_input.pdf , pages: "8-12" )
```

**한 번에 20쪽까지**이고, 돌아온 이미지에는 **쪽 번호가 없다** — 세지 말고 각 쪽 코너의
노란 `Slide N` 각인을 읽어라. `prep.json`의 `read_windows`가 창을 미리 계산해 두고
파일 경계에서 끊어 준다.

`pages`를 생략하면 통째로 첨부되고 텍스트 레이어까지 오는데, **쪽이 많으면 거부된다** —
49쪽에서 `Maximum 20 pages per request`로 막혔고 33쪽은 됐다. 문턱을 모르니 통째 읽기를
기대하지 말고 창으로 나눠 읽는 것을 기본으로 삼아라.

색은 나오지 않는다. 필기자마다 규약이 달라 같은 색이 정반대를 뜻하기 때문이다.
뜻은 색이 아니라 `annotations.json`의 `notes`에 적힌 **말**에 있다.
`signals`의 `stamp`는 출제 이력 도장, `pasted_image`는 붙여넣은 캡처다. 섞지 마라.

**서브에이전트에게 채널을 명시하라.** 지정하지 않으면 에이전트가 필기가 살아 있는
`media/`로 우회한다. 강의록은 `model_input.pdf`, 족보는 `annotated.pdf`라고
파일명으로 적어라.

### 0.5단계 — 구조 판별 (Opus 5 호출 ⓪)

띄우기 직전에 `timings.py ... start 0.5-model`, 받은 직후에 `end 0.5-model`.

`quiz` 스킬과 **같은 단계, 같은 산출물**이다. 이미 `structure.json`이 있고 같은 PDF에서
나온 것이면 다시 돌리지 않는다.

족보 경계는 문구 정규식으로 못 잡는다. 표지가 "정답"이면 낱말 목록에 없어 놓치고,
문항이 annotation 이미지뿐이면 빈 페이지 폴백도 안 걸린다. 실제로 네 강의 연속으로
**모델이 힌트를 뒤집었고**(한 장 늦음·한 장 이름·세 장 이름) 방향이 일정하지 않아
보정도 못 했다. 그래서 힌트를 아예 없앴다.

필기자가 적어 둔 말은 좋은 단서지만, **문구를 경계로 착각하지 마라.**

> "여기서부터는 작년 선배님의 필기에서 가져왔습니다"

이건 **자료의 출처가 바뀌는 지점**이지 족보가 시작되는 지점이 아니다. 이 문구가
슬라이드 N에 있어도 그 앞장이 이미 족보인 경우가 있다. 문구는 "이 근처"라는 신호로만
쓰고, 어디서 갈리는지는 앞뒤 페이지에서 **문항 번호·5지선다·정답표가 어디서 시작하는지**로
가려라.

> `runs/<lecture_id>/page_features.json`과 `outline.json`을 읽어라. 그다음
> `annotated.pdf`를 **전 페이지** 읽어라 — 경계를 찾는 자리이므로 뒤쪽만 봐서는 안 된다.
> `read_windows`대로 `pages`를 나눠 부른다(20쪽이 넘으면 통째 읽기가 거부된다).
> 강의록 뒷부분과 족보가 섞여 있고, 어디서 갈리는지를 네가 정한다.
>
> 판정을 `runs/<lecture_id>/structure.json`에 쓴다.
>
> - `lecture_range` `[1, N]` · `jokbo_range` `[N+1, 끝]` 또는 `null` — 겹치지도
>   비지도 않게
> - `jokbo_evidence` — 왜 거기서 갈리는지 한 줄. 슬라이드 번호를 대라
> - `chunks` — 강의록의 주제 덩어리. `lecture_range`를 빠짐없이·겹침없이 덮는다
>
> 슬라이드 번호는 세지 말고 **각인된 노란 `Slide N` 라벨을 읽어서** 적어라.
> 헷갈리면 `jokbo_range`를 넓게 잡지 말고 좁게 잡아라 — 강의록을 족보로 오인하면
> 필기 없는 clean 채널을 잃는다.

```bash
python quiz/structure.py runs/<lecture_id>
```

**불평이 하나라도 나오면 그 단계를 다시 시킨다.** 손으로 JSON을 고쳐 넘기지 마라.

### 1단계 — 예습 청사진 (Opus 5 호출 ①)

띄우기 직전에 `timings.py ... start 1-blueprint`, 받은 직후에 `end 1-blueprint`.

`general-purpose` 서브에이전트. **문항은 만들지 않는다.** 무엇을 확인할지만 정한다.

`structure.json`의 `lecture_range`·`jokbo_range`가 이 단계의 범위다. `chunks`는 이미
나뉜 주제이므로 다시 나누지 말고 그 위에 `check_point`를 얹어라.

> `runs/<lecture_id>/structure.json`을 먼저 읽어 구간과 주제를 확인하라.
> **`preview.md`가 있으면 그다음으로 읽어라. 있으면 그것이 이 퀴즈의 본체다**
> (`preview-rules.md` §0.1). 학생이 강의 직전에 읽을 예습 대화이고, 무엇을 물을지는
> 거기서 고른다. 없으면 이 줄은 무시한다.
> `model_input.pdf`를 **강의록 범위만큼 전부** 읽어라 (20쪽을 넘으면 나눠 부른다).
> `outline.json`과 `annotations.json`도 읽어라.
> 그다음 `annotated.pdf`의 족보 구간을 읽어라 (`jokbo_input.pdf`가 있으면 그쪽도 —
> offset 주의). 족보의 첫 쓰임은 **우선순위 판단**이다.
> 그 위에, 족보가 §1의 다섯 우선순위를 강의록보다 선명하게 보여주는 지점이 있으면
> 그것도 `check_point`로 삼을 수 있다 (§2). **족보에 나왔다는 사실만으로는 근거가 안 된다.**
>
> `.claude/skills/prequiz/references/preview-rules.md`를 **전부** 읽어라.
> 특히 §0(목적), §1(무엇을 문항으로 만드는가), §2(범위), §4(focus).
> 청사진을 `runs/<lecture_id>/pre_blueprint.json`에 쓴다. 스키마는 `references/blueprint.schema.json`.
>
> - 이 강의가 무엇에 관한 것인지 `lecture_summary`에 3~4문장
> - 족보에서 읽어낸 성향은 `exam_focus`에. 족보 슬라이드 번호를 `slides`에 넣을 때는
>   그 내용이 중심 흐름이라는 근거를 `objective`에서 읽을 수 있어야 한다
> - 목표는 4~7개. 각 `check_point`에 `focus`(must_know / core / context)를 붙여라
> - **강의를 들어야만 알 수 있는 내용(`needs_lecture`)과 지엽적 수치(`too_detailed`)는
>   `skipped`로 뺀다.** 전자는 좌절이 되고 후자는 시험 덱 몫이다
> - 문항은 정보량대로 내되 **20개를 넘지 않는다.** `check_point` 총합도 그에 맞춘다
> - **다시 봐도 도움이 되는 지점을 골라라** (§3.2). 상한이 좁아졌으므로 무엇을
>   넣을지가 곧 무엇을 버릴지다 — 축을 세우는 자리를 먼저 잡고, 단발 조회는 뒤로

받은 뒤 직접 `pre_blueprint.json`을 열어 세 `focus`가 모두 나타나는지, `skipped`가 비어
있지 않은지 확인한다. `slides`에 족보 구간 번호가 있으면 그 `objective`가 중심 흐름을
가리키는지 직접 읽어라.

### 2단계 — 문항 작성 (Opus 5 호출 ②, **objective별 동시 실행**)

`pre_blueprint.json`의 **objective 하나에 서브에이전트 하나**를 붙여 동시에 돌린다.
조각마다 `timings.py ... start 2-write --label <obj_id>`, 받은 직후에 `end`.
**라벨을 빠뜨리지 마라** — 없으면 벽시계와 작업시간 합이 안 갈리고, 그 둘의 차가
조각화의 값이다.

**왜 objective인가.** quiz는 `structure.json`의 `chunks`로 쪼개는데 여기서는
청사진의 objective로 쪼갠다. Pre-Quiz에는 **20문항 상한**이 있어서 조각들이
서로를 모르는 채로 "정보량대로" 쓰면 합이 넘는데, **청사진이 이미 배분을 들고
있다** — 그 objective의 `check_point` 수가 그 조각의 몫이다. `250820_01`에서
check_point 총합 30에 문항 29였고 objective별로도 거의 1:1이었다.

**왜 쪼개나.** 통짜 2단계가 12.5분이고 그 안에서 죽으면 그때까지의 32분이 통째로
날아간다. 얻는 것은 시간보다 **한 번에 죽지 않는 것**이다 — 조각 하나가 죽어도
나머지는 남고, `merge_items.py`가 없는 조각을 이름으로 적어 준다.

각 조각에 이렇게 준다. `<obj_id>`와 그 objective의 `check_points`·`slides`를 박아라.

> 너는 `pre_blueprint.json`의 **`<obj_id>` 하나만** 맡는다. 그 objective의
> `check_points`를 문항으로 만들어라. **다른 objective는 건드리지 마라** — 다른
> 에이전트가 맡고 있고, 겹치면 `merge_items.py`가 경계 겹침으로 표시한다.
> 근거가 필요한 슬라이드는 강의록이면 `model_input.pdf`,
> 족보면 `annotated.pdf`에서 `pages`로 그 슬라이드만 읽어라.
> **`preview.md`가 있으면 함께 읽어라** — 학생이 읽고 올 예습 대화다.
> **대화가 정리해 준 것을 그대로 물어도 된다.** 수업 전에 외우고 들어가야 하는
> 것이 이 퀴즈의 본체다 (`preview-rules.md` §0.1).
> `.claude/skills/prequiz/references/preview-rules.md`를 **전부** 읽고 그 규칙대로 만든다.
> 결과를 `runs/<lecture_id>/pre_items.raw.<obj_id>.json`에.
> 스키마는 `references/item.schema.json`.
>
> - **네 몫은 이 objective의 `check_point` 수만큼이다.** 전체 20문항 상한은 조각들의
>   합으로 지켜지므로 네가 다른 조각의 몫을 당겨쓰면 안 된다 (§3)
> - **`id`는 적지 마라.** 조각들은 서로를 몰라 저마다 `p001`을 만든다. 번호는 3단계가 매긴다
> - 예습 대화에서 착안한 문항도 `slide_no`는 그 내용이 실린 **강의록 슬라이드**를
>   가리키고 `source_type`은 `lecture`다. 대화에만 있고 강의록에 없는 내용은 내지 마라
> - 모든 문항은 청사진의 `objective_id`와 `check_point`에 묶인다
> - `slide_no`는 페이지를 세지 말고 **각인된 노란 `Slide N` 라벨을 읽어서** 적는다.
>   `source_type`은 그 번호가 강의록 구간이면 `lecture`, 족보 구간이면 `jokbo`
> - 족보 문항은 **강의의 중심 흐름 위에 있을 때만** 낸다. 족보에 나왔다는 사실만으로는
>   근거가 안 된다 (§2). 원문을 그대로 옮기지 말고 선지에 의존하지 않게 다시 쓴다
> - 객관식 선지는 **정확히 5개, 본문만.** 번호를 적지 마라. `answer`는 `"3"` 같은
>   1-based 인덱스 문자열이다 (§7)
> - 오답 선지는 §7.2의 네 출처에서 만든다. 정답 선지만 길어지지 않게 하라
> - OX는 진술문. 참·거짓을 반반 가깝게 (§5.4)
> - `explanation`에 §8의 세 요소를 전부 담아라. 특히 **③ 강의에서 무엇을 들을 것인가**
> - 청사진의 check_point 중 문항을 만들지 않은 것은 `skipped`에 사유와 함께 남긴다

조각이 다 돌아오면 합친다.

```bash
python prequiz/merge_items.py runs/<lecture_id>
```

objective 순서대로 이어 붙인다. **정렬하지 않는다** — Pre-Quiz는 슬라이드 순이
아니라 작성 순서가 곧 푸는 순서다(`PreItem.ord`).

`✗ 조각이 없다`가 뜨면 그 objective의 문항이 통째로 빠진 것이다. **그 조각만**
다시 돌리면 된다 — 나머지는 그대로 쓴다. 그러라고 쪼갠 것이다.

`두 조각이 같이 다룬 슬라이드`와 `check_point N개와 다르다`는 **표시일 뿐이다.**
지울지 채울지는 4단계가 정한다.

### 3단계 — 기계 검증 (코드)

```bash
python prequiz/validate.py runs/<lecture_id>
```

`pre_items.checked.json`(빌드 가능)과 `pre_suspects.json`(감사 대상)이 나온다.
출력의 문항 수·유형 분포·focus 분포·출처 분포·정답 번호 편중을 사용자에게 한 줄로 보고한다.

`source_type_range_mismatch`가 대량으로 나오면 문항이 아니라 **0.5단계의 족보 경계가
틀린 것**이다. `structure.json`을 다시 판정시켜라 — 다시 렌더할 필요는 없다.
경계는 포인터일 뿐이라 `structure.json`만 고치면 검증·빌드가 그걸 따른다.

### 4단계 — 감사 (Opus 5 호출 ③)

띄우기 직전에 `timings.py ... start 4-audit`, 받은 직후에 `end 4-audit`.

새 `general-purpose` 서브에이전트로 돌린다. 자기가 쓴 걸 자기가 의심하기는 어렵다고
보고 나눈 것인데 **아직 실측하지 않았다** ([docs/pipeline.md](../../../docs/pipeline.md) 4단계).

> `pre_suspects.json`과 `pre_items.checked.json`을 읽어라. 원본 확인이 필요하면
> 강의록은 `model_input.pdf`, 족보는 `annotated.pdf`에서 `pages`로 지목된 슬라이드만 읽어라.
> `.claude/skills/prequiz/references/preview-rules.md`의 **§12 감사 기준**을 따른다.
> **패치만** `runs/<lecture_id>/pre_audit_patch.json`에, 판정 근거를 `pre_audit.md`에 쓴다.
> 최종 배열을 통째로 쓰지 마라 — 형식은 `prequiz/apply_audit.py` 첫머리에 있다.
> `edit`은 바꿀 필드만, `drop`은 id와 사유, `add`는 새 문항. **언급하지 않은 문항은
> 전부 유지다.** 합치는 일은 코드가 한다.
>
> - `flagged` — 수정 / 유지 / 삭제 중 하나
> - `longest_choice_is_answer`·`lazy_distractor` — 선지를 §7.2의 출처로 다시 만든다
> - `thin_explanation` — §8의 세 요소, 특히 ③을 채운다
> - `answer_position_bias` — 정답 위치를 옮기고 선지 순서를 재배치한다.
>   **`answer` 인덱스도 함께 바꿔야 한다**
> - `near_duplicate_groups` — 예습은 자리가 좁다. 의심되면 지운다
> - `hot_slides` — 한 슬라이드 3문항 초과분은 가장 지엽적인 것부터 버린다
> - `coverage_gaps` — `must_know` 지점이 비어 있으면 반드시 채운다
> - `jokbo_item_is_context` — 그 족보 문항이 정말 중심 흐름인지 다시 보라. `focus`를 올릴
>   근거가 없으면 지운다 (§2)
> - `source_type_range_mismatch` — `slide_no`와 `source_type` 중 어느 쪽이 틀렸는지
>   원본 라벨로 가려라
> - `untouched_slides` — **대부분 정상이다.** §1의 다섯 우선순위에 해당하는지만 확인하라
> - 최종 문항 수가 20을 넘으면 잘라 20 이하로 맞춘다. **무엇을 남기는지는 §3.2** —
>   `context`부터가 기본이되, 축을 세우는 문항보다 단발 조회를 먼저 버린다

받은 뒤 패치를 반영하고 **검증을 한 번 더 돌린다.**

```bash
python prequiz/apply_audit.py runs/<lecture_id>                              # 패치 → pre_items.final.json
python prequiz/validate.py runs/<lecture_id> --items pre_items.final.json    # 다시 통과하는지
```

고친 것이 정말 고쳐졌는지는 확정본을 검증해 봐야 안다. `hard 제거`가 하나라도 나오면
빌드 불가 문항이 섞인 것이므로 4단계로 되돌린다 — `studyez.gate`가 그 자리를
배포 검문으로 쓴다.

`add`한 문항은 **맨 뒤에 붙는다.** Pre-Quiz는 슬라이드 순이 아니라 작성 순서가
곧 푸는 순서라(`PreItem.ord`), 코드가 임의로 끼워 넣지 않는다.

`없는 id를 가리켰다`가 뜨면 감사가 존재하지 않는 문항을 고치려 한 것이다. 그
문항이 정말 필요하면 4단계를 다시 시켜라 — 패치를 손으로 고치지 마라.

### 5단계 — 빌드 (코드)

```bash
python prequiz/build.py runs/<lecture_id>
```

`slide_no`가 범위를 벗어나거나 이미지가 없으면 **빌드가 중단된다.**
임의로 번호를 바꾸지 말고 4단계로 되돌려 원본에서 확인시켜라.

### 6단계 — 올린다 (코드)

```bash
python -m studyez done <lecture_id>
```

`<lecture_id>`는 방금 돌린 **작년** run이다. 서버에서 이 예습이 붙는 자리는
**올해 강의**이므로 `studyez.matching`이 그 짝을 찾아 올린다. 짝이 확정이 아니면
올리지 않고 그렇게 적는다 — 어긋난 짝을 붙이면 남의 강의 예습이 올라간다.

올해 그 강의가 아직 안 올라왔으면 "붙일 자리가 없다"고 적고 끝난다. **정상이다.**
산출물은 그대로 두면 되고, 올해 필기가 올라온 뒤 야간 쓸어담기가 같이 민다.

작년 run에는 표시(`source.json`)를 찍지 않는다 — 표시는 올해 필기를 다시 안
만들려는 장치라 작년 run에 찍으면 아무 데도 안 쓰인다.

슬라이드 이미지(`media/*.png`, 편당 12~27MB)는 **Pre-Quiz가 있는 편에만** 따라
올라간다. 웹 오답 해설이 `slide_no`로 그것을 찾는 유일한 소비자다.

## 사용자 보고

- 덱 이름(`...::예습확인`), 문항 수, 유형 분포(객관식/단답/OX), focus 분포(필수/핵심/맥락)
- 출처 분포(강의록/족보)와 족보가 물었던 지점을 다룬 문항 수(`exam_hit`)
- 감사에서 삭제/수정/보충한 수
- 청사진에서 `needs_lecture`·`too_detailed`로 뺀 내용 중 **학생이 알아둘 만한 것 한두 개**
- **단계별 소요** — `python quiz/timings.py runs/<lecture_id> report`의 표를 그대로 붙인다
- `.apkg` 경로. Anki에서 수동 import한다 (자동 투입하지 않는다)

## 실패 시

- 서브에이전트가 스키마를 어긴 JSON을 쓰면 그 단계만 다시 시킨다. 손으로 JSON을 고쳐 넘기지 않는다
- 문항이 30을 넘어 나오면 2단계 지시가 아니라 1단계 청사진이 비대한 것이다. §1의 제외 사유를
  강조해 1단계부터 다시 돌린다
- `source_type_range_mismatch`가 대량이면 0.5단계부터 다시. 렌더는 그대로 두면 된다
- 족보 문항이 지엽적 기출로 채워지면 §2의 '중심 흐름' 조건이 1단계에서 무시된 것이다.
  2단계가 아니라 1단계부터 다시 돌린다
- 사용자가 문항 품질을 지적하면 `references/preview-rules.md`의 해당 절을 직접 고친다.
  다음 실행부터 세 에이전트가 그 규칙을 읽는다
