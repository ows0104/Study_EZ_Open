# 기생충학 땡시 마스터 데이터

문항 생성의 단일 진실 공급원(single source of truth). 이미지·문항은 이 테이블을 참조한다.

## 파일 구조

```
data/
  species/     01_nematoda … 06_arthropoda.json   ← 편집은 여기서
  specimens/   01_eggs … 04_gross_arthropoda.json ← 편집은 여기서
  glossary.json                                    ← 구조물 용어 변형·오답 용어
  species.json / specimens.json                    ← 자동 생성 (병합본)
  species.csv  / specimens.csv                     ← 자동 생성 (엑셀 검토용)
scripts/
  build_master.py                                  ← 병합 + 검증 + CSV 내보내기
```

빌드·검증:

```bash
uv run --python 3.13 python scripts/build_master.py
```

`species.json` / `specimens.json` / `*.csv` 는 생성물이므로 직접 고치지 말 것. 항상 `species/`, `specimens/` 하위 파일을 고치고 다시 빌드한다.

## 왜 두 개의 테이블인가

땡시 한 문항은 **종**이 아니라 **표본** 하나를 보여준다. 같은 회충이라도 `수정란`, `불수정란`, `성충 육안`, `성충 단면`은 서로 다른 문항이 되고, 감별점도 오답 후보도 전부 다르다. 그래서 축을 나눴다.

- `species` — 그 종에 대한 지식. 감염경로·감염형·숙주·증상·진단·치료. **문제의 정답과 해설**이 여기서 나온다.
- `specimens` — 현미경/육안으로 보이는 것. 감별점·구조물·혼동 대상. **문제의 사진과 보기**가 여기서 나온다.

## species 스키마

| 필드 | 설명 |
|---|---|
| `id` | snake_case 고유키. specimens에서 FK로 참조 |
| `scientific_name` | 정명 |
| `aliases` | 족보에 등장한 오타·이표기 (`Ascarus lumbricoides`, `Hook worm` 등). 족보 자동 파싱용 |
| `group` | `선충` `흡충` `조충` `원충` `말라리아` `의용곤충` 중 하나 |
| `transmission_mode` | `토양매개성` `식품매개성` `접촉매개성` `패류매개성` `절지동물매개성` `수인성` `성접촉` `공기매개` — "전파 방식은?" 문항의 보기 세트가 여기서 나옴 |
| `transmission_route` / `source` / `infective_stage` | "무엇을 먹으면 감염되나?" "감염형은?" 문항용 |
| `intermediate_host` / `definitive_host` / `habitat` / `lung_migration` | "종숙주는?" "기생 부위는?" 문항용 |
| `disease_ko` / `disease_en` | "이 기생충에 의한 병명은?" 문항용 |
| `symptoms` / `diagnosis` / `treatment` | 증상·진단·치료 문항 및 해설용 |
| `vector_for` | 의용곤충 전용. "이 생물이 매개하는 질환은?" 문항용 |
| `exam_notes` | 출제 포인트 한 줄 요약. 해설에 그대로 쓸 수 있게 작성 |
| `distractor_only` | `true`면 실습 표본이 없고 보기(오답)로만 쓰이는 종 |

## specimens 스키마

| 필드 | 설명 |
|---|---|
| `id` | snake_case 고유키 |
| `species_id` | species FK |
| `specimen_type` | `충란` `충체` `조직` `gross` `혈액도말` |
| `stage` | `fertilized egg`, `filariform larva`, `gravid proglottid`, `ring form` 등 |
| `label_ko` / `label_en` | 정답 문자열 |
| `size_um` / `size_group` | 충란 크기 문항 및 계측 문항용. `size_group`은 실습에서 쓰는 30/60/90um 묶음 |
| `stain` / `magnification` | 문제 지문에 표시할 염색법·배율 |
| `key_features` | 감별점. **해설의 본문** |
| `structures` | indicator로 지시할 수 있는 구조물 목록. **indicator 문항(족보 43건)의 정답 풀** |
| `confusable_with` | 혼동하기 쉬운 다른 표본/종의 id. **오답 보기 생성의 1순위 후보** |

## 문항 유형별 데이터 매핑

족보 9개년 330문항을 분석한 유형과, 각 유형이 쓰는 필드:

| 유형 | 족보 빈도 | 정답 | 오답 보기 |
|---|---|---|---|
| 충란/종 동정 | 116 | `specimen.label_en` | `confusable_with` → 같은 `size_group` → 같은 `group` |
| indicator 구조물 | 43 | `specimen.structures[i]` | 같은 표본의 다른 구조물 → `confusable_with` 표본의 구조물 → `glossary.fake_distractors` |
| 감염경로/감염원 | 24 | `species.source` | 다른 종의 `source` |
| 감염형/발육단계 | 22 | `species.infective_stage` | 다른 `infective_stage` 값 |
| 증상·질병명 | 15 | `species.disease_ko` / `symptoms` | 같은 `group` 내 다른 종 |
| 매개질환(곤충) | 13 | `species.vector_for` | 다른 곤충의 `vector_for` |
| 치료 | 6 | `species.treatment[0]` | 다른 계열 구충제 |
| 숙주·기생부위 | 6 | `definitive_host` / `habitat` | — |

오답은 `confusable_with`를 1순위로 쓴다. 같은 분류군 안에서 실제로 헷갈리는 것끼리 묶여야 시험 난이도가 재현되기 때문이다.

## 검증 규칙

`build_master.py`가 자동으로 잡는다.

- id·학명 중복
- 필수 필드 누락
- `species_id` 미해결 FK
- `confusable_with` 미해결 참조
- 허용되지 않은 `group` / `specimen_type` 값
- `distractor_only`인데 표본이 연결된 모순, 표본이 없는데 `distractor_only`가 아닌 종

## 알려진 표기 문제

족보와 정리본에 오타·구표기가 섞여 있어 정명으로 통일하고 원표기는 `aliases`에 남겼다.

| 정명 | 자료에 등장한 표기 |
|---|---|
| *Endolimax nana* | Entamoeba nana, Entameoba nana |
| *Pneumocystis jirovecii* | Pneumocystis carinii (carinii는 쥐 감염종) |
| *Trichuris trichiura* | Trichuris trichuria |
| *Giardia lamblia* | Girardia lambila |
| *Gymnophalloides seoi* | Gynecophalloides seoi |
| lateral cord | lateral chord |
| gynecophoral canal | gynechophoral canal |

## 현재 규모

종 68건 / 표본 102건 / 구조물 121종 / 이미지 854장(문제 사용가능 775장) / 복원 족보 279문항(객관식 270) / 생성 문항 6,461개 / 웹 앱 36MB.

족보 보기에 등장한 학명 83종 중 73종이 매칭되며, 나머지 10종은 학명이 아닌 병리 소견 문구(`Necrosis of…`)와 구조물 표기 변형이다.

---

# 이미지 파이프라인

```bash
uv run --python 3.13 python scripts/extract_images.py   # xlsx -> images/ + image_manifest.json
uv run --python 3.13 --with pillow python scripts/map_images.py   # -> images.json, coverage.csv
```

`extract_images.py`는 엑셀 "셀 안의 그림"(rich value)을 꺼낸다. 이 그림들은 일반 drawing이 아니라
`metadata.xml → rdrichvalue.xml → richValueRel.xml.rels → xl/media/` 체인으로 연결되어 있어
openpyxl로는 읽히지 않는다. 추출물은 `images/<source>/<sheet>/<행>_<셀>.png`에 저장된다.

`map_images.py`는 행 라벨을 종·표본에 붙인다. 원본 라벨에 학명 오타가 많아
정확 일치 → 퍼지 매칭 → 속명 순으로 단계적으로 좁히고, 시트명과 염색법으로 표본 유형을 정한다.

## data/images.json 필드

| 필드 | 설명 |
|---|---|
| `path` | `images/` 기준 상대경로 |
| `species_id` / `specimen_id` | 매핑 결과 |
| `section` | `실습`(학생이 실제로 본 슬라이드) / `강의록` / `기타` |
| `confidence` | `high` 확정 · `medium` 유형만 추정 · `low` 확인 필요 |
| `kind` | `photo` / `diagram`(생활사 모식도 — 문제에 쓰지 않음) |
| `width` / `height` / `quiz_usable` | 해상도와 사용 가능 여부 |
| `name_ko` / `name_en` / `stage` / `features` | 원본 행 라벨 (추적용) |

`quiz_usable`은 표본에 매핑됐고 · 모식도가 아니고 · 짧은 변이 250px 이상일 때만 참이다.

## image_overrides.json

라벨만으로는 나눌 수 없는 행(한 행에 편절과 두절이 같이 들어 있는 경우 등)을
이미지를 직접 확인해 판정한 결과. 키는 `<source>/<sheet>/<cell>`이고
값이 `diagram`이면 표본 사진이 아니라는 뜻이다. 매핑의 마지막 단계에서 덮어쓴다.

## 주의

`images/`는 371MB다. 그대로 커밋하지 말고 배포 단계에서 필요한 것만 리사이즈해서 옮길 것.

---

# 족보 복원

```bash
uv run --python 3.13 --with pymupdf python scripts/parse_jokbo.py   # PDF -> past_questions.json + questions/
uv run --python 3.13 python scripts/link_questions.py               # -> past_questions_linked.json, exam_frequency.*
```

## 족보 PDF를 읽을 때 걸리는 것들

- **2단 조판**이고 읽는 순서는 왼쪽 단 전체 → 오른쪽 단 전체다. x=300을 경계로 나눈다.
- **문항 번호는 마침표(`1.`), 보기 번호는 닫는 괄호(`1)`)** 를 쓴다. 이게 둘을 가르는 유일한 신호다.
  보기 표기는 해마다 다르다: `1)`(2017·2019·2021·2023) / `가.`(2022) / `• 가 :`(2015) / `①`(2025).
- **정답표가 문제와 같은 페이지의 반대쪽 단**에 들어있는 해가 있다(2016-1은 p47 오른쪽 단).
  그래서 정답표 판별은 페이지가 아니라 **단 단위**로 한다.
- 정답 표기도 해마다 다르다: 번호(2019·2021·2023·2025), 가나다(2022),
  **답 텍스트**(2016-1·2017 — "Trichuris trichiura", "접촉성"), `(3)`, `(2) 돼지고기`.
- 2016-2는 사진도 보기도 없는 **복원 목록**이라 문항으로 만들 수 없다. `recall_lists`로 따로 담았다.
- 2026 족보는 머리글이 "…2026 족보"라 `땡시` 패턴에 안 걸린다. 별도로 처리한다.

## past_questions_linked.json 필드

| 필드 | 설명 |
|---|---|
| `year` / `no` / `stem` / `options` | 연도·번호·지문·보기 |
| `answer_index` / `answer_raw` / `answer_text` | 정답 번호와 원문 표기 |
| `correct_text` | 실제 정답 문자열 (보기에서 뽑거나 답 텍스트) |
| `format` | `mcq` · `short_answer`(보기 없이 정답만) · `unrestored` |
| `qtype` | 13종 문항 유형 |
| `image_paths` | `questions/` 기준 상대경로 |
| `answer_species_id` / `answer_specimen_id` / `answer_structure` / `answer_stage` | 마스터 테이블 연결 |
| `answer_kind` | `species` · `structure` · `stage` · `other` |
| `option_species_ids` | 보기에 등장한 종 전부 (오답 후보 학습용) |

## exam_frequency.json

`answer_count`(정답으로 나온 횟수), `years`, `recent_year`, `option_count`(보기로 등장한 횟수),
그리고 `exam_weight = sqrt(정답횟수 + 1)`. 참고 레포(Neuro Spotter)와 같은 가중치 공식이라
문항 표집 로직을 그대로 쓸 수 있다. 한 번도 정답이 아니었던 종도 가중치 1.0으로 남겨둔다.

`option_count`가 `answer_count`보다 훨씬 큰 종(편충 22:4, 요코가와흡충 20:4)은
**정답보다 오답 보기로 훨씬 자주 쓰인 종**이라는 뜻이다. 오답 생성기가 참고할 값이다.

---

# 세 번째 이미지 소스와 구멍 메우기

## 실제실습본 PDF

```bash
uv run --python 3.13 --with pymupdf python scripts/extract_practical_pdf.py
```

99페이지 · 사진 323장. 셀 내장 이미지가 아니라 **inline image**라 bbox로 잘라낸다.
라벨은 페이지 제목에서 얻는데, 그냥 상단 텍스트를 쓰면 두 곳에서 틀린다.

- **한 페이지에 두 종이 오는 경우**(p91 = P. ovale + Pneumocystis). 페이지당 제목 하나가 아니라
  **사진마다 바로 위 제목**을 찾아야 한다.
- **이어지는 페이지의 제목 자리에 캡션이 오는 경우**(`male`, `40x`, `Schizont`).
  이때는 앞 제목을 이어써야 한다.

그래서 제목 후보를 **마스터 종 테이블로 검증**해서, 종으로 풀리는 줄만 제목으로 인정한다.
이 검증을 넣기 전에는 p68(Sparganum)이 앞 페이지의 D. latum으로, p92-93(Pneumocystis)이
P. ovale로 잘못 붙었다.

PDF 안의 섹션 표지(연충란/선충류/흡충류/조충류/원충)를 찾아 페이지마다 `topic`을 붙인다.
`topic`이 `충란`이면 그 페이지 사진은 전부 충란이다 — 이 신호가 없으면
충란 섹션 사진이 성충·조직으로 잘못 분류된다.

### 잘라낸 자리에 남의 것이 딸려 온다

`page.get_pixmap(clip=bbox)`는 그 사진을 꺼내는 것이 아니라 **그 자리에 있는 것을
전부 그린다.** 그래서 두 가지가 같이 구워진다.

| | 323장 중 |
|---|---:|
| 다른 사진과 겹쳐 옆 사진 조각이 딸려 들어옴 | 141장 |
| 크롭 안에 PDF 텍스트가 들어감 (구조물 이름·종 이름) | 152장 |
| 둘 중 하나라도 해당 | 216장 |

문제로 쓰는 실제실습본 사진 277장 중 **184장**이 여기 걸린다. 눈에 보이는 증상은
"사진 한 귀퉁이에 흰 네모가 붙어 있다"와 "사진에 답이 적혀 있다" 둘이다.
`scripts/audit_questions.py --pdf`가 센다.

고치려면 페이지를 그리지 말고 **박힌 이미지 스트림을 그대로 꺼내야 한다**
(`get_image_info(xrefs=True)` → `doc.extract_image(xref)`). 다만 그렇게 꺼낸 것은
PDF가 잘라 보여주던 부분이 아니라 원본 전체라, 다시 꺼낸 뒤 `map_images.py`부터
새로 돌려야 한다.

정리한 사람이 사진 자체에 그려 넣은 화살표와 글씨는 이 방법으로도 안 지워진다 —
그건 래스터의 일부다.

## 이미지가 없는 표본 6건

세 소스 어디에도 사진이 없다. 오답 보기로는 쓸 수 있지만 문제 사진으로는 못 쓴다.

| 표본 | 사유 |
|---|---|
| 이의 충란 (서캐) | 어느 자료에도 없음 |
| 분선충 간상유충 | 실습 슬라이드가 사상유충뿐 |
| 단방조충 성충 | 슬라이드가 protoscolex·낭벽뿐 |
| 주혈흡충 간 조직절편 | 실습에서 성충만 관찰 |
| 요충 성충 (육안) | 현미경 표본만 존재 |
| 옴진드기 피부 조직절편 | 마운트 표본만 존재 |

## 보기 생성 (fill_gaps.py)

```bash
uv run --python 3.13 python scripts/fill_gaps.py
```

족보에 지문·사진·정답은 있는데 보기가 없는 문항 39개의 보기를 채운다.
2016-1이 29개로 가장 많다 — 그 해 족보는 보기를 아예 싣지 않고 정답만 텍스트로 적었다.

오답은 지어내지 않는다. **같은 유형의 다른 해 문항에 실제로 쓰인 보기**에서 뽑고,
정답이 종이면 그 종 표본의 `confusable_with`를 1순위로 쓴다.
감염경로 문항은 정답이 전파방식이면 전파방식끼리, 감염원 음식이면 음식끼리만 묶는다.
계측·혈액도말 실기 문항은 객관식이 아니므로 건드리지 않는다.

채운 문항은 `options_generated: true`로 표시되므로 원본 보기와 구분된다.

## 끝내 복원할 수 없는 것

족보 자체가 "복원 안됨"으로 비워둔 문항 21개(2021년 9개, 2022년 10개, 2016-1 2개)는
정답표에도 없고 2026 실습 필기본의 족보 섹션도 같은 족보를 스크린샷한 것이라 자료가 없다.
2018·2020·2024년 족보는 애초에 존재하지 않는다(흡충 필기본에 명시).

---

# 문항 생성기

```bash
uv run --python 3.13 python scripts/generate_exam.py --sets 5 --questions 40 --seed 20260906
```

출력: `data/generated_exams.json`, `data/generated_preview.txt`

## 구성비는 족보에서 가져온다

문항 유형과 분류군 비율은 복원한 279문항의 실제 비율을 그대로 쓴다.
표집 가중치는 `exam_frequency.json`의 `sqrt(정답횟수+1)` — 참고 레포와 같은 공식이라
간흡충(w=3.61)이 왜소조충(w=1.0)보다 3.6배 자주 나온다.

문항 순서는 실제 시험처럼 충란 → 선충 → 흡충 → 조충 → 원충 → 말라리아 → 의용곤충.

## 오답은 지어내지 않는다

| 정답 종류 | 오답 출처 (우선순위) |
|---|---|
| 종 | 표본의 `confusable_with` → 같은 분류군 (족보 `option_count` 높은 순) |
| 구조물 | 같은 표본의 다른 구조물 → 혼동 표본의 구조물 → `glossary.fake_distractors` |
| 감염경로·감염형·병명 등 | 같은 분류군 다른 종의 같은 필드 값 |

`exclude_distractors`가 있는 표본은 그 종을 오답에서 뺀다. 구충란 문제에
*Necator americanus*가 오답으로 들어가면 사실상 정답이 두 개가 되기 때문이다.
같은 이유로 구충란·유무구조충란·유무구조충 육안은 `answer_label`을 따로 둬서
정답이 `Hookworm`, `Taenia spp.`가 되게 했다.

## 종까지 안 갈리는 표본에는 종 지식을 못 묻는다

구충란과 유무구조충란은 **사진으로 종이 갈리지 않는다.** 그래서 정답을
`Hookworm`, `Taenia spp.`로 두고 갈라지는 종을 `exclude_distractors`에 넣었다.

그런데 감염형·병명 같은 종 지식 문항은 표본의 `species_id` **하나만** 보고
만들어져 왔다. 유무구조충 충란 사진에 "인체 감염형은?"을 물으면 정답이
유구낭미충으로 나가지만, 사진이 유구/무구를 안 가르므로 무구낭미충도 맞다.

`Generator.same_across()`가 갈라지는 종들이 **같은 값**을 가질 때만 내게 한다.

| | 유구/무구/아시아조충 | 결과 |
|---|---|---|
| 기생부위 | 소장 = 소장 = 소장 | 낸다 |
| 종숙주 | 사람 = 사람 = 사람 | 낸다 |
| 치료 | Praziquantel 셋 다 | 낸다 |
| 전파방식 | 식품매개성 셋 다 | 낸다 |
| 감염원 | 돼지고기 / 소고기 / 돼지 간 | **뺀다** |
| 감염형 | 유구낭미충 / 무구낭미충 / 내장낭미충 | **뺀다** |
| 병명 | 유구조충증 / 무구조충증 / 아시아조충증 | **뺀다** |
| 진단 | 대변검사 / 대변검사 / 편절 형태 | **뺀다** |

이 규칙으로 36문항이 빠졌다(6,461 → 6,425). 구충란은 두 종의 값이 거의 같아
거의 다 남는다.

## 보기끼리 포함관계가 되면 안 된다

정답이 맞아도 **좁은 쪽 보기를 고른 사람을 틀렸다고 할 수 없는** 조합이 있다.

```
종숙주는?   ① 사람   ② 사람·소   ③ 개   ④ 쥐        <- ①과 ②가 동시에 참
기생 부위?  ① 소장   ② 소장 상부  ...                <- 같은 문제
감염형은?   ① 포낭   ② 4핵성 포낭 ...                <- 같은 문제
```

`generate_exam.contains()`가 보기를 **낱말 집합**으로 바꿔 부분집합이면 버린다.
순서와 조사는 무시하므로 `충란에 오염된 손·음식`과 `유구조충 충란에 오염된 음식·손`도
같이 걸린다.

**글자 단위로 보면 안 된다.** `회충증`⊂`고래회충증`, `scolex`⊂`protoscolex`,
`cyst`⊂`intracystic body`는 서로 다른 답인데 글자로는 포함관계다. 그래서
`·` `/` `,` `→` `-` 괄호 공백으로 가른 낱말 단위로만 본다.

이 규칙을 넣기 전 6,461문항 중 **960문항**에 포함관계가 있었고(그중 665문항은
정답이 관계에 껴 복수정답), 넣은 뒤 0이 됐다. 오답 후보 풀이 충분히 깊어
문항 수는 그대로다.

## 사진을 고르는 기준

`quiz_usable`(표본 확정 + 250px 이상)에 더해 생성기가 세 가지를 더 건다.

1. **`실습` 섹션만.** 강의록·기타 열에는 교과서 삽화와 생활사 모식도가 섞여 있다.
2. **선명도 하위 10% 제외.** 회색조 경계 강도로 잰다. 빈 시야·초점이 나간 사진이 걸린다.
3. **모식도·정답 노출 사진 제외.** 흰 배경 + 무채색이면 잉크 선화로 자동 판정하고,
   표본병에 종 이름이 적힌 육안 사진 9장은 `image_overrides.json`에 `exclude`로 등록했다.
   (`Taenia saginata`라고 쓰인 병 사진을 보여주고 종을 물으면 문제가 되지 않는다.)

같은 표본이라도 문항마다 사진을 바꾼다. 늘 같은 사진이 나오면 여러 세트를 풀 때
사진을 외워버리기 때문에, 선명한 쪽 절반 안에서 골라 쓴다.

## indicator 문항 — 화살표가 실제로 있는 사진만 쓴다

땡시의 indicator는 사진에 그린 화살표가 아니라 **현미경 접안렌즈에 걸린 선분**이다.
2017년 족보 7번이 그렇게 설명한다 — "파란색 선분으로 보입니다. 대개 양쪽 눈 중
한쪽에만 설치되어 있습니다."

처음에는 "행 라벨에 구조물 이름이 있으면 그 사진에는 화살표가 그려져 있을 것"으로
보고 냈다. **사진을 열어 보니 아니었다.**

| 사진 출처 | 그때 낸 문항 | 실제 상태 |
|---|---:|---|
| 실제실습본 | 64 | 화살표는 있는데 **옆에 이름이 같이 적혀 있다** — 답이 사진에 있다 |
| 그 밖(정리본·통합) | 60 | **화살표가 아예 없다** — 무엇을 묻는지 알 수 없다 |

지금은 두 곳에서만 가져온다.

### 1. 실제실습본 — 이름을 가리고 다시 잘라낸다 (22문항)

```bash
uv run --python 3.13 --with pymupdf python scripts/extract_indicators.py
```

화살표는 PDF의 **벡터 도형**이고 이름은 **텍스트**라 서로 다른 것이다. 이름 자리에만
리댁션을 걸고 다시 그리면 화살표는 남고 답은 사라진다. 겹쳐 들어오는 옆 사진도 같이
덮는다. 결과는 `images/practical_ind/`와 `data/indicator_images.json`.

문항이 되는 조건은 넷이다 — 화살표가 있고 · 크롭 안 글씨에서 구조물 이름이 정확히
하나 나오고 · 그 구조물이 표본의 `structures`에 있고 · **화살표가 덮은 자리로 향하지
않는다.** 323장 중 32장이 통과하고, 그중 22장이 표본의 구조물과 맞는다.

> `draw_rect`로는 안 된다. 이 PDF는 페이지 내용 스트림이 `q`를 닫지 않고 끝나서
> 뒤에 붙인 그리기가 그 그래픽 상태에 딸려 화면 밖으로 나간다. 리댁션은 내용
> 스트림을 다시 쓰므로 그 영향을 받지 않는다.

버려진 18장 중 일부는 **매핑 오류를 드러낸다** — `macronucleus`가 리슈만편모충
사진에 붙은 것 등(macronucleus는 대장아메바의 것이다). 구조물이 표본에 없으면
문항으로 안 내지만, 그 목록은 `scripts/extract_indicators.py`를 돌리면 보인다.

### 2. 족보 — 진짜 indicator가 찍혀 있다 (33문항)

`data/past_questions_linked.json`의 indicator 문항 중 사진·보기·정답이 다 있는 것을
**그대로** 가져온다(`build_web.past_indicator`). 지문도 보기도 실제 시험의 것이다.

표본 연결은 구조물 이름으로 되짚는다. `ovary`처럼 여러 종에 걸치는 구조물은 사진을
봐야 갈리므로 **연결하지 않고 비운다** — 33문항 중 26건이 연결되고 7건은 분류군이
없다. 앱은 그것을 '미상'으로 세고, 없는 표본을 있다고 하지 않는다.

화살표가 필요 없는 `특징 구조물`로 흡수한다.

화살표가 필요 없는 `특징 구조물` 유형("이 기생충이 가진 특징적 구조물은?")을 따로 둬서
indicator 후보가 모자랄 때 대신 쓴다. 족보에도 같은 형태의 문항이 있다.

## 문항 수는 '표본 × 유형 × 사진'이다

```
6,461개 = 사진 555장 × 그 표본에 붙는 유형들
```

땡시는 결국 **사진을 알아보는 시험**이라 같은 질문이라도 사진이 다르면 다른 문제다.
그래서 사진을 축에 넣었다. 사진마다 오답 조합과 지문도 다르게 뽑는다
(같은 표본·유형이라도 사진이 다르면 보기가 달라지는 비율 82%).

중복은 두 겹으로 막는다.

- **한 세트 안** — 같은 표본은 두 번 나오지 않는다. 사진만 다른 같은 문제가
  한 시험지에 들어가는 걸 막는다.
- **세트 사이** — 이미 낸 (표본·유형·사진) 조합은 후순위로 미룬다.
  10세트 400문항을 뽑아도 완전히 같은 문항은 0개다.

보기 순서는 브라우저가 풀 때마다 새로 섞는다. 위치를 외우는 걸 막기 위해서다.

문항 축을 늘려온 과정:

| 늘린 것 | 전 | 후 |
|---|---:|---:|
| 특징 구조물 (표본당 첫 구조물 1개 → 전부) | 83 | 190 |
| 감염경로 (감염원 + 전파방식 두 변형) | 90 | 179 |
| 진단 (새 유형, 족보에 있던 유형) | 0 | 90 |
| 사진을 축에 추가 (표본×유형 → 표본×유형×사진) | 1,049 | **6,461** |

전파방식은 족보 분류상 감염경로에 속하므로 별도 유형으로 만들지 않고
같은 유형 안의 변형으로 넣었다. 그래야 족보에서 뽑은 구성비가 흔들리지 않는다.

중간숙주는 만들다가 뺐다. 자료의 값이 `패류`처럼 뭉뚱그려져 있어
정답 `쇠우렁`과 상하위 관계가 되기 때문이다.

## 문항 순서: 분류군 순이 아니다

처음에는 충란 → 선충 → 흡충 → 조충 → 원충 → 말라리아 → 의용곤충 순으로 정렬했다.
복원한 족보로 확인해보니 **근거가 없었다.**

| | 족보 8개년 |
|---|---|
| 분류군 순 정렬 | 아니오 — 전 연도 섞여 있음 |
| 충란 앞쪽 배치 | 예 — 5개년 예외 없이 앞에 몰림 |

```
2025  란란란란란란란체조조체조혈육      <- 충란 블록은 앞
2025  선조흡흡선흡선선흡원원조원조원조말말곤   <- 분류군은 섞임
```

그래서 충란만 앞으로 빼고 나머지는 섞는다. 웹 앱에는 '완전 랜덤' 옵션도 뒀다.

## 구조물 문항의 함정

`indicator`와 `특징 구조물`은 오답 생성 규칙이 달라야 한다.

- **indicator** — 화살표가 하나를 짚어주므로 같은 표본의 다른 구조물도 정상적인 오답이다.
- **특징 구조물** — "이 기생충이 가진 구조물은?"이므로 그 표본이 가진 구조물은 **전부 정답**이다.
  같은 표본 것을 오답으로 쓰면 정답이 여러 개가 된다.

혼동 표본에서 가져온 구조물이 우연히 이 표본에도 있는 경우(`operculum` 등)까지
걸러야 완전히 막힌다. 이걸 놓쳐서 한동안 83문항에 복수정답이 있었다.

## 사진에 답이 들어 있는지 Claude에게 물어 보기

```bash
uv run --python 3.13 --with anthropic python scripts/screen_questions.py --limit 50
```

동정 문항이 **사진만으로 풀리는지**를 모델에게 물어 추린다. 묻는 것은 "정답이
무엇이냐"가 아니라 **"사진이 똑같이 받쳐 주는 다른 보기가 있느냐"**다. 정답이
그 목록에 끼면 그 문항은 사진으로 안 갈린다.

`ANTHROPIC_API_KEY`가 필요하다. 결과는 `data/screen_results.jsonl`(다시 돌리면
이어서 한다)과 사람이 볼 `data/screen_flagged.csv`.

**모델이 틀린 것과 문항이 깨진 것은 다르다.** 판정이 아니라 추려 주는 장치이고,
걸린 것만 사진을 열어 보면 된다. 거꾸로는 조금 더 믿을 만하다 — 모델이 사진만으로
자신 있게 맞혔다면 사진에 근거가 있다는 뜻이다.

## 감사 스크립트

```bash
uv run --python 3.13 python scripts/audit_questions.py
uv run --python 3.13 --with pymupdf python scripts/audit_questions.py --pdf
```

"정답이 맞느냐"가 아니라 **"이 문항이 성립하느냐"**를 본다 — 보기 포함관계,
흐린 사진, 매핑 신뢰도, indicator 상태. 그리고 동정 문항에 실제로 쓰인
정답↔오답 쌍 451개를 `data/identification_pairs.csv`로 내보낸다. 두 종이 사진으로
갈리는지는 기계가 모르므로, 사람이 보고 못 가르는 줄에 표시해
`exclude_distractors`로 옮기는 자리다.

## 현재 산출

10세트 400문항 기준: 세트 안 표본 중복 0, 세트 간 완전 동일 문항 0,
서로 다른 사진 311장, 정답 위치 분포 105/110/94/91.

---

# 웹 앱

```bash
uv run --python 3.13 --with pillow python scripts/build_web.py   # -> web/quiz_db.js, web/images/
uv run --python 3.13 python -m http.server 8811 --directory web  # 로컬에서 보기
```

정적 파일 3종(`index.html`, `quiz_db.js`, `images/`)뿐이라 빌드 도구가 없다.
자세한 내용은 [web/README.md](../web/README.md).

**문항 조립은 브라우저에서** 한다. 오답 생성은 마스터 테이블을 봐야 하므로
`build_web.py`가 763개 문항을 미리 완성해 넘기고, 브라우저는 거기서
출제빈도로 가중 표집만 한다. 덕분에 세트는 무한히 뽑을 수 있으면서
오답 품질은 서버에서 검증한 그대로다.

사진은 900px·JPEG 80%로 줄여 335장 20MB. 원본 `images/`(605MB)는 배포하지 않는다.
