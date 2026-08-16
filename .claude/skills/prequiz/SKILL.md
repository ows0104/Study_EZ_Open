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
| 언제 | 강의 후, 시험 대비 반복 | 강의 직전 1회 점검 |
| 분량 | 슬라이드당 여러 장 | 강의당 **12~20문항** |
| 형식 | 앞·뒤 회상 카드, cloze | 객관식 5지선다 / 단답 / OX |
| 족보 | 문항으로 출제 | 우선순위 판단에 쓰고, **강의의 중심 흐름 위에 있을 때만** 출제 |
| 산출 | `<강의>.apkg` | `<강의>_예습.apkg` (하위 덱 `::예습확인`) |

같은 `runs/<lecture_id>/`를 공유하되 파일 이름이 `pre_`로 갈린다. 서로 덮어쓰지 않는다.

## 역할 경계 (어기지 말 것)

| | 코드 (`quiz/prep.py`, `prequiz/`) | 모델 (이 스킬) |
|---|---|---|
| 하는 일 | PDF 자르기·각인·렌더, 족보 구간 분리, 선지 번호 부여, 스키마·범위·중복·선지 검사, 덱 패키징 | 무엇을 물을지, 어떻게 물을지, 무엇을 버릴지 |
| 안 하는 일 | 의미 판단 일절 | 파일명·이미지·ID·선지 번호 조작 일절 |

선지 번호 ①②③④⑤는 **코드가 붙인다.** 모델은 선지 본문과 정답 인덱스까지만 적는다.

## 실행 절차

인자로 받은 강의 PDF 경로를 `<pdf>`라 한다. 인자가 없으면 아래에서 목록을 보여주고 묻는다.

    ~/SynologyDrive/{과목}/필기/{연도}/[YYMMDD_NN]제목(교수)_필기자vN.pdf

Pre-Quiz는 **작년** 필기가 대상이다. 족보가 정리돼 붙어 있는 쪽이 작년이다.
올해 강의에 대응하는 작년 파일은 `python -m studyez match {과목}`이 알려준다.

아래 `python`은 이 환경에서 PATH에 없다. 실제로는 `PYTHONIOENCODING=utf-8
"C:/Users/ows01/anaconda3/python.exe"` 로 부르고, 작업 디렉터리는 이 저장소 루트다.

### 0단계 — 준비 (코드)

```bash
python quiz/prep.py "<pdf>"
```

`quiz` 스킬과 **같은 스크립트, 같은 출력**이다. `runs/<lecture_id>/prep.json`이 이미 있고
같은 PDF에서 나온 것이면 다시 돌리지 않아도 된다.

`runs/<lecture_id>/`에 생기는 것:

- `model_pages/clean_sNNN.png` — **전 페이지.** 필기 제거 + `Slide N` 각인. 출제의 본체
- `jokbo_pages/jokbo_sNNN.png` — **뒤 절반.** 우선순위 판단용이자, 중심 흐름일 때는 출제 대상
- `page_features.json` — 페이지별 글자수·annotation·답안 나열·족보 낱말·**붙여넣은 이미지 수**. 0.5단계 입력
- `jokbo_text.md` — `--jokbo-pdf`를 줬을 때만. 원본 족보의 원문 텍스트
- `outline.json` / `annotations.json` — 슬라이드별 본문 요약, 필기·형광펜·**도장(stamp)** 신호
- `media/` — Anki 카드 뒷면용 슬라이드 PNG
- `prep.json` — `jokbo_hint`, `slide_image_map` 등 계약 파일

**두 채널이 겹쳐서 렌더된다.** clean은 전 페이지, annotated는 뒤 절반이다. 경계가
어디로 정해지든 다시 렌더하지 않게 하려는 것이다. `prep.json`의 `jokbo_hint`는
**힌트일 뿐이고 경계의 주인은 0.5단계다.**

색은 나오지 않는다. 필기자마다 규약이 달라 같은 색이 정반대를 뜻하기 때문이다.
뜻은 색이 아니라 `annotations.json`의 `notes`에 적힌 **말**에 있다.
`signals`의 `stamp`는 출제 이력 도장, `pasted_image`는 붙여넣은 캡처다. 섞지 마라.

**서브에이전트에게 채널을 명시하라.** 이 환경에는 poppler가 없어 Read 툴이 PDF 페이지를
렌더하지 못한다. 채널을 지정하지 않으면 에이전트가 필기가 살아 있는 `media/`로 우회한다.

### 0.5단계 — 구조 판별 (Opus 5 호출 ⓪)

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
> `jokbo_pages/jokbo_sNNN.png`를 **전부** 읽어라. 강의록 뒷부분과 족보가 섞여 있고,
> 어디서 갈리는지를 네가 정한다.
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

`general-purpose` 서브에이전트. **문항은 만들지 않는다.** 무엇을 확인할지만 정한다.

`structure.json`의 `lecture_range`·`jokbo_range`가 이 단계의 범위다. `chunks`는 이미
나뉜 주제이므로 다시 나누지 말고 그 위에 `check_point`를 얹어라.

> `runs/<lecture_id>/structure.json`을 먼저 읽어 구간과 주제를 확인하라.
> **`preview.md`가 있으면 그다음으로 읽어라. 있으면 그것이 이 퀴즈의 본체다**
> (`preview-rules.md` §0.1). 학생이 강의 직전에 읽을 예습 대화이고, 무엇을 물을지는
> 거기서 고른다. 없으면 이 줄은 무시한다.
> `model_pages/clean_sNNN.png`를 **강의록 범위만큼 전부** 읽어라.
> `outline.json`과 `annotations.json`도 읽어라.
> 그다음 `jokbo_pages/`의 족보 이미지를 읽어라. 족보의 첫 쓰임은 **우선순위 판단**이다.
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
>   반드시 `skipped`로 뺀다.** 이게 예습 퀴즈의 가장 흔한 실패다
> - `check_point` 총합이 25를 넘지 않게 하라. 문항은 12~20개다

받은 뒤 직접 `pre_blueprint.json`을 열어 세 `focus`가 모두 나타나는지, `skipped`가 비어
있지 않은지 확인한다. `slides`에 족보 구간 번호가 있으면 그 `objective`가 중심 흐름을
가리키는지 직접 읽어라.

### 2단계 — 문항 작성 (Opus 5 호출 ②)

새 `general-purpose` 서브에이전트.

> `pre_blueprint.json`을 읽고, 근거가 필요한 슬라이드는 강의록이면 `model_pages/`,
> 족보면 `jokbo_pages/`에서 읽어라.
> **`preview.md`가 있으면 함께 읽어라** — 학생이 읽고 올 예습 대화다. 문항은 그
> 대화를 이해했는지 찌른다 (`preview-rules.md` §0.1).
> `.claude/skills/prequiz/references/preview-rules.md`를 **전부** 읽고 그 규칙대로 만든다.
> 결과를 `runs/<lecture_id>/pre_items.raw.json`에. 스키마는 `references/item.schema.json`.
>
> - **12~20문항.** 객관식 8~12 / 단답 3~5 / OX 2~4 (§3)
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

새 `general-purpose` 서브에이전트. **문항을 쓴 에이전트를 재사용하지 마라.**

> `pre_suspects.json`과 `pre_items.checked.json`을 읽어라. 원본 확인이 필요하면
> 강의록은 `model_pages/`, 족보는 `jokbo_pages/`에서 해당 슬라이드만 읽어라.
> `.claude/skills/prequiz/references/preview-rules.md`의 **§12 감사 기준**을 따른다.
> 최종 배열을 `runs/<lecture_id>/pre_items.final.json`에, 판정 근거를 `pre_audit.md`에 쓴다.
>
> - `flagged` — 수정 / 유지 / 삭제 중 하나
> - `longest_choice_is_answer`·`lazy_distractor` — 선지를 §7.2의 출처로 다시 만든다
> - `thin_explanation` — §8의 세 요소, 특히 ③을 채운다
> - `answer_position_bias` — 정답 위치를 옮기고 선지 순서를 재배치한다.
>   **`answer` 인덱스도 함께 바꿔야 한다**
> - `near_duplicate_groups` — 문항이 12~20개뿐이다. 의심되면 지운다
> - `hot_slides` — 한 슬라이드 3문항 초과분은 가장 지엽적인 것부터 버린다
> - `coverage_gaps` — `must_know` 지점이 비어 있으면 반드시 채운다
> - `jokbo_item_is_context` — 그 족보 문항이 정말 중심 흐름인지 다시 보라. `focus`를 올릴
>   근거가 없으면 지운다 (§2)
> - `source_type_range_mismatch` — `slide_no`와 `source_type` 중 어느 쪽이 틀렸는지
>   원본 라벨로 가려라
> - `untouched_slides` — **대부분 정상이다.** §1의 다섯 우선순위에 해당하는지만 확인하라
> - 최종 문항 수가 20을 넘으면 `context`부터 잘라 20 이하로 맞춘다

### 5단계 — 빌드 (코드)

```bash
python prequiz/build.py runs/<lecture_id>
```

`slide_no`가 범위를 벗어나거나 이미지가 없으면 **빌드가 중단된다.**
임의로 번호를 바꾸지 말고 4단계로 되돌려 원본에서 확인시켜라.

## 사용자 보고

- 덱 이름(`...::예습확인`), 문항 수, 유형 분포(객관식/단답/OX), focus 분포(필수/핵심/맥락)
- 출처 분포(강의록/족보)와 족보가 물었던 지점을 다룬 문항 수(`exam_hit`)
- 감사에서 삭제/수정/보충한 수
- 청사진에서 `needs_lecture`·`too_detailed`로 뺀 내용 중 **학생이 알아둘 만한 것 한두 개**
- `.apkg` 경로. Anki에서 수동 import한다 (자동 투입하지 않는다)

## 실패 시

- 서브에이전트가 스키마를 어긴 JSON을 쓰면 그 단계만 다시 시킨다. 손으로 JSON을 고쳐 넘기지 않는다
- 문항이 30개 넘게 나오면 2단계 지시가 아니라 1단계 청사진이 비대한 것이다. §1의 제외 사유를
  강조해 1단계부터 다시 돌린다
- `source_type_range_mismatch`가 대량이면 0.5단계부터 다시. 렌더는 그대로 두면 된다
- 족보 문항이 지엽적 기출로 채워지면 §2의 '중심 흐름' 조건이 1단계에서 무시된 것이다.
  2단계가 아니라 1단계부터 다시 돌린다
- 사용자가 문항 품질을 지적하면 `references/preview-rules.md`의 해당 절을 직접 고친다.
  다음 실행부터 세 에이전트가 그 규칙을 읽는다
