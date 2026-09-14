# 표본

서버·웹이 붙을 실제 산출물이다. 파이프라인을 돌리지 않고도 화면을 만들 수 있게
고정해 둔다. 모양이 궁금하면 `../artifact-contract.md`를 함께 보라.

| 파일 | 무엇 | 어디서 나왔나 |
|---|---|---|
| `pre_items.sample.json` | 웹에서 푸는 예습 카드 28장 | 병리학 `250825_01` 종양의 분자생물학(1) |
| `pre_run.meta.sample.json` | 예습 덱의 요약 | 같은 편 (28장 · 웹 풀이 28장) |
| `run.meta.sample.json` | 복습 덱의 요약. 관리자 화면이 "배포해도 되는가"를 판단하는 값 | 병리학 `260820_03` 소아질환의 병태생리(2) (88장) |

전부 `quizgen` → `studyez.deck.contract`가 낸 것이다.

## `pre_items.sample.json`에서 놓치기 쉬운 것

- **자유회상 카드다. 보기가 없다.** 채점은 서버가 아니라 본인이 한다 — 답을 펴 보고
  맞았다/틀렸다를 찍는다. 그래서 `POST .../prequiz/reveal`이 따로 있고, `grade`는
  `correct` 불리언을 받는다
- `qtype`은 `basic`·`cloze`·`ox` 셋이다. 푸는 방식은 셋 다 같고 화면이 꼴만 달리 그린다.
  **표본에는 `ox`가 없다** — 예습 덱에서 드물게 나오는 형식이라 한 편에 없을 수 있다
- `cloze`의 `stem`은 이미 빈칸으로 펴져 있다. `{{c1::…}}`은 Anki의 문법이라 웹에
  그대로 내보내지 않고 `contract()`가 `[____]`(힌트가 있으면 `[힌트]`)로 바꾼다.
  원문은 `items.reproduced.json`에 그대로 남는다
- `focus`는 **왜 이것이 「꼭 반드시」인가**다 — `spine`·`vocabulary`·`mechanism`·
  `clinical`·`repeated`. 등급이 아니다. 예습 카드는 전부 「꼭 반드시」이고, 등급을
  두면 그 축이 흐려진다
- **그림 카드는 여기 없다.** 앞면이 이미지라 텍스트만으로는 물음이 성립하지 않는다
  (`이 조직은 어느 장기이며…`). apkg에는 그대로 들어 있고, 몇 장이 빠졌는지는
  `pre_run.meta.json`의 `web_excluded`가 든다
- `slide_no`로 근거 슬라이드를 띄우려면 `slides/`도 함께 올라가야 한다

## `run.meta.sample.json`에서 볼 것

- `verified`는 **apkg를 다시 열어 센 값**이다. `item_count`와 어긋나면 덱이 내용과
  다른 것을 담고 있다는 뜻이고, `studyez.gate`가 막는 몇 안 되는 것 중 하나다
- `reproduce`는 질문만 보고 다시 푼 결과다. `same`이 아니어도 나쁜 카드는 아니다 —
  눈가리개 세션이 그 지식을 몰랐을 수 있다. **문항 자체의 결함으로 갈린 것은
  파이프라인이 이미 덱에서 뺐고**, 그래도 남아 있으면 `reproduce_defects`에 뜬다
- `review_flagged`는 검토 표시가 붙은 카드 수, `review_flags`가 그 종류다.
  종류가 사람을 부르는 신호이지 개수가 아니다
- `slides_unused`는 카드가 하나도 없는 슬라이드 전부다(표지·학습목표가 여기 든다).
  진짜 누락 신호는 **선언된 건너뜀을 이미 뺀** `untouched_slides` 쪽이다
- `lecture_id` 필드 이름은 역사적인 것이고 값은 `run_id`다. `deck_id`가 quizgen의
  ID(`p260820_03`)이고 그쪽이 guid의 씨앗이다

## 갱신

파이프라인이 바뀌어 모양이 달라지면 여기도 같이 갱신한다. 계약이 움직이면
`../artifact-contract.md`를 먼저 고치고 그다음 표본을 바꾼다.

```bash
python -m studyez import --from ../PDF2ANKI/out --run-id 260820_03
```
